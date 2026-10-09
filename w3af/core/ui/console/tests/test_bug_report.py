"""
test_bug_report.py

Copyright 2012 Andres Riancho

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
import shutil
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from w3af import ROOT_PATH
from w3af.core.controllers.misc.file_lock import FileLock
from w3af.core.ui.console.console_ui import ConsoleUI
from w3af.core.ui.console.tests.helper import ConsoleTestHelper

CRASH_PAGE = "crash2.html"
INDEX_BODY = f'<html><body><a href="{CRASH_PAGE}">crash</a></body></html>'.encode()
CRASH_BODY = b"<html><body>boom</body></html>"


class BuggyCrawlSite:
    """
    A local web application whose index links to a page that makes the
    failing_spider test plugin raise an exception while crawling.
    """

    def __init__(self):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), self._handler_class())
        self.server.daemon_threads = True
        self._thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    @property
    def url(self):
        return f"http://127.0.0.1:{self.server.server_address[1]}/"

    def start(self):
        self._thread.start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()

    @classmethod
    def serve_for(cls, test_case):
        site = cls()
        site.start()
        test_case.addCleanup(site.close)
        return site

    def _handler_class(self):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                body = CRASH_BODY if self.path.endswith(CRASH_PAGE) else INDEX_BODY
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        return Handler


class TestConsoleBugReport(ConsoleTestHelper):
    """
    Run a scan from the console UI which fails with a bug, and drive the
    bug-report menu over the resulting exception.
    """

    def setUp(self):
        # The plugin manager only discovers plugins living in plugins/crawl,
        # so the failing_spider test plugin is copied there for the scan.
        self.src = os.path.join(
            ROOT_PATH, "plugins", "tests", "crawl", "failing_spider.py"
        )
        self.dst = os.path.join(ROOT_PATH, "plugins", "crawl", "failing_spider.py")

        self.lock = FileLock(self.dst, timeout=60)
        self.lock.acquire()
        shutil.copy(self.src, self.dst)

        super().setUp()
        self.site = BuggyCrawlSite.serve_for(self)

    def tearDown(self):
        if os.path.exists(self.dst):
            os.remove(self.dst)
        if os.path.exists(self.dst + "c"):
            os.remove(self.dst + "c")
        self.lock.release()
        super().tearDown()

    def _run_buggy_scan(self, extra_commands):
        commands_to_run = [
            "plugins",
            "output console",
            "crawl failing_spider",
            "crawl config failing_spider",
            "set only_forward true",
            "back",
            "back",
            "target",
            f"set target {self.site.url}",
            "back",
            "start",
            "bug-report",
            *extra_commands,
            "exit",
        ]

        self.console = ConsoleUI(commands=commands_to_run, do_upd=False)
        self.console.sh()

    def test_summary_and_details(self):
        self._run_buggy_scan(["summary", "list", "details 0"])

        caught_exceptions = self.console._w3af.exception_handler.get_all_exceptions()
        self.assertEqual(len(caught_exceptions), 1, self._mock_stdout.messages)

        expected = (
            "During the current scan (with id: ",
            'A "FailingSpiderError" exception was found while running',
        )
        assert_result, msg = self.startswith_expected_in_output(expected)
        self.assertTrue(assert_result, msg)

        # The list command printed the single exception with its id
        self.assertTrue(
            any("failing_spider" in line for line in self._mock_stdout.messages)
        )

        self.console._w3af.exception_handler.clear()

    def test_report_without_exceptions(self):
        self._run_buggy_scan([])

        self.console._w3af.exception_handler.clear()
        self.clear_stdout_messages()

        report_commands = [
            "bug-report",
            "report",
            "details",
            "details abc",
            "list unknown_phase",
            "exit",
        ]
        self.console = ConsoleUI(commands=report_commands, do_upd=False)
        self.console.sh()

        expected = (
            "There are no exceptions to report for this scan.",
            "The exception ID needs to be specified, please read help:",
            "The exception ID needs to be an integer, please read help:",
            "Invalid parameter type, please read help:",
        )
        assert_result, msg = self.startswith_expected_in_output(expected)
        self.assertTrue(assert_result, msg)
