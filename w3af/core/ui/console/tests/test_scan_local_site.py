"""
test_scan_local_site.py

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

import io
import unittest
from contextlib import redirect_stdout

from w3af.core.data.kb.knowledge_base import DBKnowledgeBase
from w3af.core.ui.console.console_ui import ConsoleUI
from w3af.tests.helpers.home_dir import use_temporary_home
from w3af.tests.helpers.sqli_site import PRIVATE_IP, SQLInjectionSite


class TestConsoleScanLocalSite(unittest.TestCase):
    """
    Run a complete scan from the console UI against a local web application
    """

    def setUp(self):
        use_temporary_home(self)
        kb.cleanup()
        self.site = SQLInjectionSite.serve_for(self)

    def scan_commands(self):
        return [
            "plugins",
            "crawl web_spider",
            "crawl config web_spider",
            "set only_forward True",
            "back",
            "audit sqli",
            "grep private_ip",
            "back",
            "target",
            f"set target {self.site.url}",
            "back",
            "start",
            "exit",
        ]

    def run_console(self):
        console = ConsoleUI(commands=self.scan_commands(), do_upd=False)
        output = io.StringIO()

        with redirect_stdout(output):
            console.sh()

        return console, output.getvalue()

    def test_scan_reports_findings(self):
        console, output = self.run_console()

        for vulnerable_url in self.site.vulnerable_urls():
            self.assertIn(
                f'SQL injection in a MySQL database was found at: "{vulnerable_url}"',
                output,
            )

        self.assertIn(f'contains the private IP address: "{PRIVATE_IP}"', output)
        self.assertIn("Found 4 URLs and 6 different injections points", output)
        self.assertIn("Scan finished in ", output)

        exceptions = console._w3af.exception_handler.get_all_exceptions()
        self.assertEqual([e.get_summary() for e in exceptions], [])


kb = DBKnowledgeBase()
