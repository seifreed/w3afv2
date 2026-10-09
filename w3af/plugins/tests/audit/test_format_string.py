"""
test_format_string.py

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

FORMAT_URL = "http://mock/audit/format_string/"

APACHE_500 = (
    "<!DOCTYPE HTML PUBLIC>\n<html><head>\n"
    "<title>500 Internal Server Error</title>\n"
    "</head><body><h1>Internal Server Error</h1></body></html>"
)


def format_string(mock_response, request, uri, response_headers):
    """A CGI which passes the id parameter as the printf format."""
    if "%" in request_param(request, "id"):
        response_headers["Content-Type"] = "text/html"
        return 500, response_headers, APACHE_500
    return html_page(response_headers, "Item 1")


def always_failing(mock_response, request, uri, response_headers):
    response_headers["Content-Type"] = "text/html"
    return 500, response_headers, APACHE_500


class TestFormatString(PluginTest):

    target_url = f"{FORMAT_URL}format_string.php"

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(re.compile(f"{target_url}.*"), format_string),
        MockResponse(re.compile(f"{FORMAT_URL}broken.php.*"), always_failing),
    ]

    config: ClassVar[dict] = {"audit": (PluginConfig("format_string"),)}

    def test_found_format(self):
        self._scan(self.target_url + "?id=1", self.config)

        vulns = self.kb.get("format_string", "format_string")
        self.assertEqual(1, len(vulns))

        vuln = vulns[0]
        self.assertEqual("Format string vulnerability", vuln.get_name())
        self.assertEqual(self.target_url, str(vuln.get_url()))
        self.assertEqual("id", vuln.get_token_name())

    def test_error_in_original_response_is_ignored(self):
        self._scan(f"{FORMAT_URL}broken.php?id=1", self.config)

        self.assertEqual([], self.kb.get("format_string", "format_string"))
