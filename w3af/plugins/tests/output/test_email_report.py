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

import re
import urllib.parse
from typing import ClassVar

import pytest

from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest
from w3af.plugins.tests.output.smtp_server import LocalSMTPServer


def _reflect_xss(mock_response, request, uri, response_headers):
    """Reflect the `text` parameter unescaped, emulating a reflected XSS."""
    response_headers["content-type"] = "text/html"
    query = urllib.parse.urlsplit(request.uri).query
    text = urllib.parse.parse_qs(query).get("text", [""])[0]
    body = f"<html><body>You searched for: {text}</body></html>"
    return 200, response_headers, body


@pytest.mark.moth
class TestEmailReport(PluginTest):

    target_url = "http://mock/audit/xss/"
    to_addrs = "w3af@mailinator.com"
    from_addr = "w3af@gmail.com"

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(
            target_url,
            body='<html><body><a href="xss_1.py?text=1">one</a></body></html>',
            method="GET",
        ),
        MockResponse(
            re.compile(r"http://mock/audit/xss/xss_1\.py.*"),
            body=_reflect_xss,
            method="GET",
        ),
    ]

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
