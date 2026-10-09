"""
test_buffer_overflow.py

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

BO_URL = "http://mock/bo.c"
STACK_SIZE = 800
CRASH_SIZE = 2000


def stack_smashing(mock_response, request, uri, response_headers):
    """A CGI which copies buf into a fixed size stack buffer."""
    if len(request_param(request, "buf")) > STACK_SIZE:
        return html_page(response_headers, "*** stack smashing detected ***:")
    return html_page(response_headers, "A regular body without errors")


def process_crash(mock_response, request, uri, response_headers):
    """A server whose process dies, closing the connection, on long input."""
    if len(request_param(request, "buf")) > CRASH_SIZE:
        raise ConnectionResetError("The server process crashed")
    return html_page(response_headers, "A regular body without errors")


def buffer_overflow_config():
    return {"audit": (PluginConfig("buffer_overflow"),)}


class TestBufferOverflow(PluginTest):

    target_url = BO_URL

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(re.compile(f"{BO_URL}.*"), stack_smashing),
    ]

    def test_found_bo(self):
        self._scan(self.target_url + "?buf=", buffer_overflow_config())

        vulns = self.kb.get("buffer_overflow", "buffer_overflow")
        self.assertEqual(1, len(vulns))

        vuln = vulns[0]
        self.assertEqual("Buffer overflow vulnerability", vuln.get_name())
        self.assertEqual("buf", vuln.get_token_name())
        self.assertEqual(self.target_url, str(vuln.get_url()))

    def test_error_in_original_response_is_ignored(self):
        long_buf = "B" * (STACK_SIZE + 1)
        self._scan(f"{self.target_url}?buf={long_buf}", buffer_overflow_config())

        self.assertEqual([], self.kb.get("buffer_overflow", "buffer_overflow"))


class TestBufferOverflowCrash(PluginTest):

    target_url = BO_URL

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(re.compile(f"{BO_URL}.*"), process_crash),
    ]

    def test_connection_reset_is_potential_bo(self):
        self._scan(self.target_url + "?buf=", buffer_overflow_config())

        infos = self.kb.get("buffer_overflow", "buffer_overflow")
        self.assertEqual(1, len(infos))

        info = infos[0]
        self.assertEqual("Potential buffer overflow vulnerability", info.get_name())
        self.assertEqual("buf", info.get_token_name())
