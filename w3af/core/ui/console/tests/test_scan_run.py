"""
test_scan_run.py

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

import pytest

from w3af.core.ui.console.console_ui import ConsoleUI
from w3af.core.ui.console.tests.helper import ConsoleTestHelper
from w3af.tests.helpers.sqli_site import SQLInjectionSite


@pytest.mark.smoke
class TestScanRunConsoleUI(ConsoleTestHelper):
    """
    Run scans from the console UI against a local web application.
    """

    def setUp(self):
        super().setUp()
        self.site = SQLInjectionSite.serve_for(self)

    def _sql_scan_commands(self):
        return [
            "plugins",
            "output console,text_file",
            "output config text_file",
            f"set output_file {self.OUTPUT_FILE}",
            f"set http_output_file {self.OUTPUT_HTTP_FILE}",
            "set verbose True",
            "back",
            "output config console",
            "set verbose False",
            "back",
            "audit sqli",
            "crawl web_spider",
            "crawl config web_spider",
            "set only_forward True",
            "back",
            "grep private_ip",
            "back",
            "target",
            f"set target {self.site.url}",
            "back",
            "start",
            "exit",
        ]

    def test_SQL_scan(self):
        self.console = ConsoleUI(commands=self._sql_scan_commands(), do_upd=False)
        self.console.sh()

        expected = (
            "SQL injection in ",
            "A SQL error was found in the response supplied by ",
            "Scan finished",
        )

        assert_result, msg = self.startswith_expected_in_output(expected)
        self.assertTrue(assert_result, msg)

        # The text_file output plugin really wrote the report file
        self.assertTrue(os.path.exists(self.OUTPUT_FILE))

        found_errors = self.error_in_output(["No such file or directory", "Exception"])
        self.assertFalse(found_errors)

    def test_two_scans(self):
        """
        Running a second scan after the first one finishes must work: the
        console re-enables the output plugin and cleans up the core.
        """
        scan_commands = self._sql_scan_commands()[:-1]  # drop the trailing "exit"
        scan_commands += ["cleanup"] + self._sql_scan_commands()

        self.console = ConsoleUI(commands=scan_commands, do_upd=False)
        self.console.sh()

        finished = [
            line
            for line in self._captured_stdout.messages
            if line.startswith("Scan finished")
        ]
        self.assertEqual(len(finished), 2, self._captured_stdout.messages)

        found_errors = self.error_in_output(["No such file or directory", "Exception"])
        self.assertFalse(found_errors)
