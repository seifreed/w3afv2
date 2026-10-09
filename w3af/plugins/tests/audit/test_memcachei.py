"""
test_memcachei.py

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
from w3af.plugins.tests.helper import LOREM, MockResponse, PluginConfig, PluginTest

MEMCACHE_URL = "http://mock/audit/memcache_injection/"

STORED_VALUE = "The value stored under the requested key is: 1234567890"
BAD_FORMAT_ERROR = (
    "<h1>Internal error</h1><p>The cache server answered CLIENT_ERROR"
    " bad command line format, the request could not be completed. Please"
    " contact the site administrator if the problem persists.</p>"
)
BAD_CHUNK_ERROR = "<b>Warning</b>: data chunk mismatch (code 0x22)"


def storage_command_error(key):
    """
    Emulate the memcached validation of a storage command injected in key.

    :return: The error answered by the server, None when the command is valid
    """
    lines = key.split("\r\n")
    if len(lines) == 1:
        return None

    header = lines[0].split()
    if len(header) != 4 or not all(field.isdigit() for field in header[1:]):
        return BAD_FORMAT_ERROR
    if int(header[3]) != len(lines[1]):
        return BAD_FORMAT_ERROR
    return None


def memcache_value(key):
    """Send the key to memcached without filtering CR LF."""
    return storage_command_error(key) or STORED_VALUE


def memcache_value_in_long_page(key):
    """Same as memcache_value, the result is a small part of a long page."""
    padding = LOREM * 10
    return f"{padding}<p>{memcache_value(key)}</p>{padding}"


def rejects_line_breaks(key):
    """Any key with CR LF is rejected, valid storage commands too."""
    if "\r\n" in key:
        return BAD_FORMAT_ERROR
    return STORED_VALUE


def checks_flags_only(key):
    """Only the format of the command line is validated, not the data."""
    header = key.split("\r\n")[0].split()
    if len(header) == 4 and not header[2].isdigit():
        return BAD_FORMAT_ERROR
    return STORED_VALUE


def distinct_errors(key):
    """Each memcached error is rendered in a completely different way."""
    lines = key.split("\r\n")
    if len(lines) > 1 and int(lines[0].split()[3] or 0) == 0:
        return BAD_CHUNK_ERROR
    return memcache_value(key)


def crashes_on_line_breaks(key):
    """The application dies and closes the connection on CR LF."""
    if "\r\n" in key:
        raise ConnectionResetError("The application crashed")
    return STORED_VALUE


PAGES = {
    "memcache_value.py": memcache_value,
    "memcache_value_long.py": memcache_value_in_long_page,
    "rejects_line_breaks.py": rejects_line_breaks,
    "checks_flags_only.py": checks_flags_only,
    "distinct_errors.py": distinct_errors,
    "crashes.py": crashes_on_line_breaks,
    "safe.py": lambda key: STORED_VALUE,
}


def memcache_site(mock_response, request, uri, response_headers):
    page = PAGES.get(request.uri.removeprefix(MEMCACHE_URL).split("?")[0])
    if page is None:
        return html_page(response_headers, "Not found", status=404)
    return html_page(response_headers, page(request_param(request, "key")))


class TestMemcachei(PluginTest):

    target_url = f"{MEMCACHE_URL}memcache_value.py"

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(re.compile(f"{MEMCACHE_URL}.*"), memcache_site),
    ]

    config: ClassVar[dict] = {"audit": (PluginConfig("memcachei"),)}

    def scan_page(self, page):
        self._scan(f"{MEMCACHE_URL}{page}?key=x", self.config)
        return self.kb.get("memcachei", "memcachei")

    def test_found_memcachei(self):
        vulns = self.scan_page("memcache_value.py")
        self.assertEqual(1, len(vulns))

        vuln = vulns[0]
        self.assertEqual("Memcache injection vulnerability", vuln.get_name())
        self.assertEqual(self.target_url, str(vuln.get_url()))
        self.assertEqual("key", vuln.get_token_name())

    def test_found_memcachei_comparing_page_differences(self):
        vulns = self.scan_page("memcache_value_long.py")
        self.assertEqual(["key"], [v.get_token_name() for v in vulns])

    def test_not_found_when_key_is_not_injectable(self):
        self.assertEqual([], self.scan_page("safe.py"))

    def test_not_found_when_valid_command_is_rejected(self):
        self.assertEqual([], self.scan_page("rejects_line_breaks.py"))

    def test_not_found_when_second_error_is_accepted(self):
        self.assertEqual([], self.scan_page("checks_flags_only.py"))

    def test_not_found_when_errors_differ(self):
        self.assertEqual([], self.scan_page("distinct_errors.py"))

    def test_request_errors_are_not_vulnerabilities(self):
        self.assertEqual([], self.scan_page("crashes.py"))
