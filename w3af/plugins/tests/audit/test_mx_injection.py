"""
test_mx_injection.py

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
from typing import ClassVar

from w3af.plugins.tests.audit.vulnerable_responses import html_page, request_param
from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest

MX_URL = "http://mock/audit/MX_injection/"
IMAP_ERROR = "Unexpected extra arguments to Select"


def mxi(mock_response, request, uri, response_headers):
    """A webmail which sends SELECT "<mailbox>" to the IMAP server."""
    mailbox = request_param(request, "i")
    if '"' in mailbox:
        return html_page(response_headers, f"IMAP error: {IMAP_ERROR}")
    return html_page(response_headers, f"Mailbox {mailbox} is empty")


def known_error(mock_response, request, uri, response_headers):
    return html_page(response_headers, f"The server is down: {IMAP_ERROR}")


class TestMXInjection(PluginTest):

    target_url = f"{MX_URL}mxi.php?i=f00"

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(re.compile(f"{MX_URL}mxi.php.*"), mxi),
        MockResponse(re.compile(f"{MX_URL}known_error.php.*"), known_error),
    ]

    config: ClassVar[dict] = {"audit": (PluginConfig("mx_injection"),)}

    def test_found_mxi(self):
        self._scan(self.target_url, self.config)

        vulns = self.kb.get("mx_injection", "mx_injection")

        self.assertAllVulnNamesEqual("MX injection vulnerability", vulns)
        self.assertExpectedVulnsFound([("mxi.php", "i")], vulns)

    def test_error_in_original_response_is_ignored(self):
        self._scan(f"{MX_URL}known_error.php?i=f00", self.config)

        self.assertEqual([], self.kb.get("mx_injection", "mx_injection"))
