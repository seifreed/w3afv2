"""
test_github_issues.py

Copyright 2013 Andres Riancho

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

import json
import re
import unittest

from w3af.core.controllers.ci.tests.real_state import environment_variable
from w3af.core.controllers.easy_contribution.github_issues import (
    DEFAULT_BUG_QUERY_TEXT,
    GITHUB_API_URL,
    GITHUB_CREDENTIAL_ENV_VAR,
    GithubIssues,
    LoginFailed,
    NotLoggedIn,
    OAuthTokenInvalid,
    get_oauth_token,
)
from w3af.core.controllers.tests.local_http_server import closed_local_port
from w3af.core.data.url.tests.helpers.route_server import Response, RouteServer

JSON_TYPE = "application/json"
CREDENTIAL = "unit-test-token"
REPO_PATH = "/repos/andresriancho/w3af"
ISSUE_NUMBER = 4242


def json_response(payload, status=200):
    return Response(status, json.dumps(payload), content_type=JSON_TYPE)


class TestGetOAuthToken(unittest.TestCase):
    def test_no_token_configured(self):
        with environment_variable(GITHUB_CREDENTIAL_ENV_VAR, None):
            self.assertIsNone(get_oauth_token())

    def test_empty_token_is_not_configured(self):
        with environment_variable(GITHUB_CREDENTIAL_ENV_VAR, ""):
            self.assertIsNone(get_oauth_token())

    def test_token_from_environment(self):
        with environment_variable(GITHUB_CREDENTIAL_ENV_VAR, "configured-token"):
            self.assertEqual(get_oauth_token(), "configured-token")


class GithubApiTestCase(unittest.TestCase):
    """
    Runs GithubIssues against a real local HTTP server that speaks the small
    subset of the GitHub REST API the reporter uses. Nothing is ever sent to
    github.com.
    """

    def setUp(self):
        self.api = RouteServer.serve_for(self)
        self.api.routes["/user/repos"] = json_response([])
        self.api.routes["/users/andresriancho"] = json_response(
            {"login": "andresriancho", "url": self.api.url("/users/andresriancho")}
        )
        self.api.routes[REPO_PATH] = json_response(
            {"name": "w3af", "url": self.api.url(REPO_PATH)}
        )
        self.api.add(
            "POST",
            f"{REPO_PATH}/issues",
            json_response({"number": ISSUE_NUMBER}, status=201),
        )

    def logged_in_issues(self):
        issues = GithubIssues(CREDENTIAL, base_url=self.api.base_url)
        issues.login()
        return issues

    def created_issue(self):
        posts = [r for r in self.api.requests if r.method == "POST"]
        self.assertEqual(len(posts), 1)
        return json.loads(posts[0].body)


class TestLogin(GithubApiTestCase):
    def test_login_with_valid_token(self):
        issues = GithubIssues(CREDENTIAL, base_url=self.api.base_url)

        self.assertTrue(issues.login())

        self.assertIsNotNone(issues.gh)
        request = self.api.last_request
        self.assertEqual(request.route, "/user/repos")
        self.assertIn(CREDENTIAL, request.headers["Authorization"])

    def test_default_base_url_is_github(self):
        self.assertEqual(GithubIssues(CREDENTIAL)._base_url, GITHUB_API_URL)

    def test_rejected_token_raises_oauth_token_invalid(self):
        self.api.routes["/user/repos"] = json_response(
            {"message": "Bad credentials"}, status=401
        )

        with self.assertRaises(OAuthTokenInvalid):
            GithubIssues(CREDENTIAL, base_url=self.api.base_url).login()

    def test_api_error_raises_login_failed(self):
        self.api.routes["/user/repos"] = json_response(
            {"message": "Forbidden"}, status=403
        )

        with self.assertRaises(LoginFailed):
            GithubIssues(CREDENTIAL, base_url=self.api.base_url).login()

    def test_unreachable_api_raises_login_failed(self):
        url = f"http://127.0.0.1:{closed_local_port()}"

        with self.assertRaises(LoginFailed):
            GithubIssues(CREDENTIAL, base_url=url).login()


class TestReportBug(GithubApiTestCase):
    def test_report_before_login_raises(self):
        issues = GithubIssues(CREDENTIAL, base_url=self.api.base_url)

        with self.assertRaises(NotLoggedIn):
            issues.report_bug("summary", "description")

        self.assertEqual(self.api.requests, [])

    def test_report_creates_issue_and_returns_number_and_url(self):
        issues = self.logged_in_issues()

        number, url = issues.report_bug(
            "Something broke",
            "It happens on startup",
            tback="Traceback\nValueError: boom\n",
            plugins="audit.sqli",
        )

        self.assertEqual(number, ISSUE_NUMBER)
        self.assertEqual(url, f"https://github.com/andresriancho/w3af/issues/{number}")

        issue = self.created_issue()
        self.assertEqual(
            issue["title"], "[Auto-Generated] Bug Report - Something broke"
        )
        self.assertNotIn("labels", issue)
        body = issue["body"]
        self.assertTrue(
            body.startswith("It happens on startup\n## Version Information")
        )
        self.assertIn("## Traceback\n```pytb\nTraceback\nValueError: boom\n\n```", body)
        self.assertIn("## Enabled Plugins\n```python\naudit.sqli\n```", body)

    def test_summary_defaults_to_last_traceback_line(self):
        self.logged_in_issues().report_bug(
            "", "desc", tback="Traceback (most recent call last):\nValueError: bad\n"
        )

        self.assertEqual(
            self.created_issue()["title"],
            "[Auto-Generated] Bug Report - ValueError: bad",
        )

    def test_summary_defaults_to_hash_without_traceback(self):
        self.logged_in_issues().report_bug("", "desc")

        title = self.created_issue()["title"]
        self.assertRegex(title, r"^\[Auto-Generated\] Bug Report - [0-9a-f]{32}$")

    def test_manual_reports_are_not_marked_as_generated(self):
        self.logged_in_issues().report_bug("manual", "desc", autogen=False)

        self.assertEqual(self.created_issue()["title"], "Bug Report - manual")

    def test_untouched_default_description_is_dropped(self):
        self.logged_in_issues().report_bug("s", DEFAULT_BUG_QUERY_TEXT)

        body = self.created_issue()["body"]
        self.assertTrue(body.startswith("## Version Information"))
        self.assertNotIn("What steps will reproduce the problem?", body)

    def test_plugins_section_is_omitted_without_plugins(self):
        self.logged_in_issues().report_bug("s", "d")

        self.assertNotIn("## Enabled Plugins", self.created_issue()["body"])

    def test_contact_email_is_appended_to_the_description(self):
        self.logged_in_issues().report_bug("s", "details", email="user@example.com")

        body = self.created_issue()["body"]
        self.assertIn(
            "details\n\nThe user provided the following email address for contact:"
            " user@example.com\n",
            body,
        )

    def test_version_information_lists_python_and_w3af(self):
        self.logged_in_issues().report_bug("s", "d")

        body = self.created_issue()["body"]
        match = re.search(r"```\n(.*?)\n```", body, re.DOTALL)
        self.assertIn("Python version:", match.group(1))
        self.assertIn("w3af version:", match.group(1))
