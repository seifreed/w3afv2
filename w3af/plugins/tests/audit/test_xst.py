"""
test_xst.py

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

from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest

XST_URL = "http://mock/w3af/"
SAFE_URL = "http://safe/w3af/"


def echo_trace(mock_response, request, uri, response_headers):
    """Answer TRACE echoing the received request, as RFC 9110 describes."""
    response_headers["Content-Type"] = "text/plain"
    headers = "".join(f"{name}: {value}\r\n" for name, value in request.headers.items())
    return 200, response_headers, f"TRACE {request.path} HTTP/1.1\r\n{headers}"


def trace_not_allowed(mock_response, request, uri, response_headers):
    response_headers["Content-Type"] = "text/html"
    return 405, response_headers, "Method Not Allowed"


class TestXST(PluginTest):

    target_url = XST_URL

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(re.compile(f"{XST_URL}.*"), "<html>Home</html>"),
        MockResponse(SAFE_URL, "<html>Home</html>"),
        MockResponse(re.compile(f"{XST_URL}.*"), echo_trace, method="TRACE"),
        MockResponse(re.compile(f"{SAFE_URL}.*"), trace_not_allowed, method="TRACE"),
    ]

    config: ClassVar[dict] = {"audit": (PluginConfig("xst"),)}

    def test_found_xst_once_per_scan(self):
        self._scan((XST_URL, f"{XST_URL}about.html"), self.config)

        vulns = self.kb.get("xst", "xst")
        self.assertEqual(1, len(vulns))
        self.assertEqual("Cross site tracing vulnerability", vulns[0].get_name())

    def test_trace_disabled(self):
        self._scan(SAFE_URL, self.config)

        self.assertEqual([], self.kb.get("xst", "xst"))
