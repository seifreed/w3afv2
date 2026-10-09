"""
test_ldapi.py

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

LDAP_URL = "http://mock/audit/LDAP/"
LDAP_ERROR = "LDAPException: Bad search filter"


def has_balanced_parentheses(search_filter):
    depth = 0
    for char in search_filter:
        depth += {"(": 1, ")": -1}.get(char, 0)
        if depth < 0:
            return False
    return depth == 0


def simple_ldap(mock_response, request, uri, response_headers):
    """Concatenate the i parameter into an LDAP search filter."""
    search_filter = f"(uid={request_param(request, 'i')})"
    if has_balanced_parentheses(search_filter):
        return html_page(response_headers, "No such user")
    return html_page(response_headers, LDAP_ERROR)


def known_error(mock_response, request, uri, response_headers):
    """A page which always shows the LDAP error, injection or not."""
    return html_page(response_headers, f"Maintenance: {LDAP_ERROR}")


class TestLDAPI(PluginTest):

    target_url = f"{LDAP_URL}simple_ldap.php"

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(re.compile(f"{target_url}.*"), simple_ldap),
        MockResponse(re.compile(f"{LDAP_URL}known_error.php.*"), known_error),
    ]

    config: ClassVar[dict] = {"audit": (PluginConfig("ldapi"),)}

    def test_found_ldapi(self):
        self._scan(self.target_url + "?i=xxx", self.config)

        vulns = self.kb.get("ldapi", "ldapi")
        self.assertEqual(1, len(vulns))

        vuln = vulns[0]
        self.assertEqual("LDAP injection vulnerability", vuln.get_name())
        self.assertEqual(self.target_url, str(vuln.get_url()))
        self.assertEqual("i", vuln.get_token_name())

    def test_error_in_original_response_is_ignored(self):
        self._scan(f"{LDAP_URL}known_error.php?i=xxx", self.config)

        self.assertEqual([], self.kb.get("ldapi", "ldapi"))
