"""
test_basic_auth.py

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

import base64
import os
from typing import ClassVar

import pytest

from w3af import ROOT_PATH
from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest


def _basic_auth_body(valid_credentials):
    """
    Build a MockResponse body callable that emulates HTTP basic auth: it
    returns 200 only when the request carries the expected Authorization
    header, and 401 (with a WWW-Authenticate challenge) otherwise.
    """
    expected = None
    if valid_credentials is not None:
        token = base64.b64encode(valid_credentials.encode()).decode("ascii")
        expected = f"Basic {token}"

    def respond(mock_response, http_request, uri, response_headers):
        authorization = http_request.headers.get("Authorization")
        if expected is not None and authorization == expected:
            headers = {"Content-Type": "text/html"}
            return 200, headers, "<html>Welcome admin</html>"

        headers = {
            "Content-Type": "text/html",
            "WWW-Authenticate": 'Basic realm="w3af"',
        }
        return 401, headers, "<html>401 Unauthorized</html>"

    return respond


class TestBasicAuth(PluginTest):

    target_url = "http://mock/auth/basic/weak/"
    target_url_easy = "http://mock/auth/basic/weak/"
    target_url_impossible = "http://mock/auth/basic/impossible/"

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(target_url_easy, body=_basic_auth_body("admin:admin")),
        MockResponse(target_url_impossible, body=_basic_auth_body(None)),
    ]

    BASE_PATH = os.path.join(ROOT_PATH, "plugins", "tests", "bruteforce")

    small_users_negative = os.path.join(BASE_PATH, "small-users-negative.txt")
    small_users_positive = os.path.join(BASE_PATH, "small-users-positive.txt")
    small_passwords = os.path.join(BASE_PATH, "small-passwords.txt")

    _run_configs: ClassVar[dict] = {
        "positive": {
            "target": None,
            "plugins": {
                "bruteforce": (
                    PluginConfig(
                        "basic_auth",
                        ("users_file", small_users_positive, PluginConfig.STR),
                        ("passwd_file", small_passwords, PluginConfig.STR),
                    ),
                ),
                "grep": (PluginConfig("http_auth_detect"),),
            },
        },
        "negative": {
            "target": None,
            "plugins": {
                "bruteforce": (
                    PluginConfig(
                        "basic_auth",
                        ("users_file", small_users_negative, PluginConfig.STR),
                        ("passwd_file", small_passwords, PluginConfig.STR),
                    ),
                ),
                "grep": (PluginConfig("http_auth_detect"),),
            },
        },
    }

    @pytest.mark.smoke
    def test_found_credentials(self):
        # Run the scan
        cfg = self._run_configs["positive"]
        self._scan(self.target_url_easy, cfg["plugins"])

        # Assert the general results
        vulns = self.kb.get("basic_auth", "auth")
        self.assertEqual(len(vulns), 1)

        vuln = vulns[0]

        self.assertEqual(vuln.get_name(), "Guessable credentials")

        self.assertEqual(vuln.get_url().url_string, self.target_url_easy)
        self.assertEqual(vuln["user"], "admin")
        self.assertEqual(vuln["pass"], "admin")

    def test_not_found_credentials(self):
        # Run the scan
        cfg = self._run_configs["negative"]
        self._scan(self.target_url_impossible, cfg["plugins"])

        # Assert the general results
        vulns = self.kb.get("basic_auth", "auth")
        self.assertEqual(len(vulns), 0)
