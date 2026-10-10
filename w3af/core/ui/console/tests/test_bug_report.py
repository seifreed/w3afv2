"""
test_bug_report.py

This file is part of w3af, http://w3af.org/ .

w3af is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation version 2 of the License.

w3af is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with w3af; if not, write to the Free Software
Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

"""

import os
import sys

import w3af.core.controllers.output_manager as om
from w3af.core.controllers.core_helpers.status import CoreStatus
from w3af.core.controllers.easy_contribution.github_issues import (
    GITHUB_CREDENTIAL_ENV_VAR,
    MISSING_CREDENTIAL_MSG,
    OAUTH_AUTH_FAILED,
    GithubIssues,
    LoginFailed,
    OAuthTokenInvalid,
)
from w3af.core.ui.console.bug_report import create_github_reporter
from w3af.core.ui.console.console_ui import ConsoleUI
from w3af.core.ui.console.root_menu import rootMenu
from w3af.core.ui.console.tests.helper import ConsoleTestHelper

TICKET_URL = "https://issues.example/w3af/42"


def crawl_failure():
    raise RuntimeError("web_spider failed")


def audit_failure():
    raise ValueError("sqli failed")


class InProcessIssueReporter:
    """
    An issue tracker kept in memory, with the login()/report_bug() interface
    of GithubIssues.
    """

    def __init__(self, login_error=None, ticket=(42, TICKET_URL)):
        self.login_error = login_error
        self.ticket = ticket
        self.reports = []

    def login(self):
        if self.login_error is not None:
            raise self.login_error
        return True

    def report_bug(self, summary, desc, tback=None, plugins=None):
        self.reports.append(
            {"summary": summary, "desc": desc, "tback": tback, "plugins": plugins}
        )
        return self.ticket


class TestConsoleBugReport(ConsoleTestHelper):
    """
    Drive the bug-report menu over exceptions stored by the real exception
    handler of the core, reporting them to an in-process issue tracker.
    """

    def tearDown(self):
        if self.console is not None:
            self.console._w3af.exception_handler.clear()
        super().tearDown()

    def _store_exception(self, console, phase, plugin, failure):
        status = CoreStatus(om.out)
        status.set_running_plugin(phase, plugin)
        status.set_current_fuzzable_request(phase, "http://target.example/")

        try:
            failure()
        except (RuntimeError, ValueError) as exception:
            console._w3af.exception_handler.handle(
                status, exception, sys.exc_info(), plugin
            )

    def _run(self, commands, reporter=None, exceptions=2):
        self.console = ConsoleUI(
            commands=["bug-report", *commands, "back", "exit"],
            do_upd=False,
            create_reporter=lambda: reporter,
        )
        stored = [
            ("crawl", "web_spider", crawl_failure),
            ("audit", "sqli", audit_failure),
        ][:exceptions]
        for phase, plugin, failure in stored:
            self._store_exception(self.console, phase, plugin, failure)

        self.clear_stdout_messages()
        self.console.sh()
        return "".join(self._captured_stdout.messages)

    def test_summary_list_and_details(self):
        output = self._run(
            [
                "summary",
                "list",
                "list audit",
                "list no_such_phase",
                "details",
                "details abc",
                "details 7",
                "details 1",
            ]
        )
        self.assertIn("web_spider failed", output)
        self.assertIn("sqli failed", output)
        self.assertIn("Invalid parameter type, please read help:", output)
        self.assertIn("The exception ID needs to be specified", output)
        self.assertIn("The exception ID needs to be an integer", output)
        self.assertIn("Invalid ID specified, please read help:", output)

    def test_report_all_exceptions(self):
        reporter = InProcessIssueReporter()
        output = self._run(["report"], reporter)

        self.assertEqual(
            [report["summary"] for report in reporter.reports],
            ["web_spider failed", "sqli failed"],
        )
        self.assertIn(f"[1/2] Bug with id 0 reported at {TICKET_URL}", output)
        self.assertIn(f"[2/2] Bug with id 1 reported at {TICKET_URL}", output)

    def test_report_selected_exceptions(self):
        reporter = InProcessIssueReporter()
        output = self._run(["report abc,9 1"], reporter)

        self.assertIn("Exception IDs must be integers.", output)
        self.assertIn("Exception ID out of range.", output)
        self.assertEqual(
            [report["summary"] for report in reporter.reports], ["sqli failed"]
        )

    def test_report_without_exceptions(self):
        reporter = InProcessIssueReporter()
        output = self._run(["report"], reporter, exceptions=0)

        self.assertIn("There are no exceptions to report for this scan.", output)
        self.assertEqual(reporter.reports, [])

    def test_report_without_configured_credentials(self):
        output = self._run(["report 0"])
        self.assertIn(MISSING_CREDENTIAL_MSG, output)

    def test_report_when_the_tracker_is_unreachable(self):
        reporter = InProcessIssueReporter(login_error=LoginFailed("offline"))
        output = self._run(["report 0"], reporter)
        self.assertIn("Failed to contact github.com.", output)

    def test_report_with_an_invalid_token(self):
        reporter = InProcessIssueReporter(login_error=OAuthTokenInvalid("bad"))
        output = self._run(["report 0"], reporter)
        self.assertIn(OAUTH_AUTH_FAILED.splitlines()[0], output)

    def test_report_rejected_by_the_tracker(self):
        reporter = InProcessIssueReporter(ticket=(None, None))
        output = self._run(["report 0"], reporter)
        self.assertIn("[1/1] Failed to report bug with id 0.", output)

    def test_completion(self):
        self.console = ConsoleUI(do_upd=False)
        self._store_exception(self.console, "crawl", "web_spider", crawl_failure)
        bug_report = rootMenu("w3af", self.console, self.console._w3af)
        menu = bug_report.get_children()["bug-report"]

        self.assertEqual(menu._para_details([], ""), [("", "0 ")])
        self.assertEqual(menu._para_details(["0"], ""), [])
        self.assertIn(("cr", "crawl "), menu._para_list([], "cr"))
        self.assertEqual(menu._para_list(["crawl"], ""), [])
        self.console._w3af.quit()


class TestCreateGithubReporter(ConsoleTestHelper):
    def setUp(self):
        super().setUp()
        environ = dict(os.environ)
        self.addCleanup(os.environ.update, environ)
        self.addCleanup(os.environ.clear)
        os.environ.pop(GITHUB_CREDENTIAL_ENV_VAR, None)

    def test_without_a_token(self):
        self.assertIsNone(create_github_reporter())

    def test_with_a_token(self):
        os.environ[GITHUB_CREDENTIAL_ENV_VAR] = "token-value"
        self.assertIsInstance(create_github_reporter(), GithubIssues)
