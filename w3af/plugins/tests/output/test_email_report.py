"""
test_email_report.py

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

import pytest

from w3af.core.controllers.ci.moth import get_moth_http
from w3af.plugins.tests.helper import PluginConfig, PluginTest
from w3af.plugins.tests.output.smtp_server import LocalSMTPServer


@pytest.mark.moth
class TestEmailReport(PluginTest):

    target_url = get_moth_http("/audit/xss/")
    to_addrs = "w3af@mailinator.com"
    from_addr = "w3af@gmail.com"

    def setUp(self):
        super().setUp()
        self.smtp_server = LocalSMTPServer()
        self.smtp_server.start()
        self.addCleanup(self.smtp_server.stop)

    def _plugins_config(self):
        return {
            "audit": (
                PluginConfig(
                    "xss",
                    ("checkStored", True, PluginConfig.BOOL),
                    ("numberOfChecks", 3, PluginConfig.INT),
                ),
            ),
            "crawl": (
                PluginConfig("web_spider", ("only_forward", True, PluginConfig.BOOL)),
            ),
            "output": (
                PluginConfig(
                    "email_report",
                    ("smtpServer", "127.0.0.1", PluginConfig.STR),
                    ("smtpPort", self.smtp_server.port, PluginConfig.INT),
                    ("toAddrs", self.to_addrs, PluginConfig.LIST),
                    ("fromAddr", self.from_addr, PluginConfig.STR),
                ),
            ),
        }

    def test_found_xss(self):
        self._scan(self.target_url, self._plugins_config())

        xss_vulns = self.kb.get("xss", "xss")
        inbox = self.smtp_server.inbox

        self.assertEqual(len(inbox), 1)
        email_msg = inbox[0]

        self.assertEqual(email_msg.from_address, self.from_addr)
        self.assertEqual(email_msg.to_addresses, [self.to_addrs])

        xss_count = 0
        pxss_count = 0

        for line in email_msg.message.split("\n"):
            if "A Cross Site Scripting vulnerability was found at:" in line:
                xss_count += 1
            elif "A persistent Cross Site Scripting vulnerability" in line:
                pxss_count += 1

        self.assertEqual(len(xss_vulns), xss_count + pxss_count)
