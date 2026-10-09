"""
test_unssl.py

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


class TestUnSSL(PluginTest):

    target_url = "http://httpretty/"

    # This mocked response will be returned for both http and https
    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(
            target_url,
            "foo bar spam",
        )
    ]

    _run_configs: ClassVar[dict] = {
        "cfg": {
            "target": target_url,
            "plugins": {
                "audit": (PluginConfig("un_ssl"),),
            },
        }
    }

    def test_found_unssl(self):
        cfg = self._run_configs["cfg"]
        self._scan(cfg["target"], cfg["plugins"])

        vulns = self.kb.get("un_ssl", "un_ssl")
        self.assertEqual(1, len(vulns))

        # Now some tests around specific details of the found vuln
        vuln = vulns[0]
        self.assertEqual(vuln.get_name(), "Secure content over insecure channel")
        self.assertEqual(vuln.get_url().url_string, "http://httpretty/")


class TestNotFoundUnSSL(PluginTest):

    target_url = "http://httpretty/"

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(re.compile(r"http://httpretty/$"), "This is NOT SECURE"),
        MockResponse(
            re.compile(r"https://httpretty/$"), "The banking application is here."
        ),
    ]

    _run_configs: ClassVar[dict] = {
        "cfg": {
            "target": target_url,
            "plugins": {
                "audit": (PluginConfig("un_ssl"),),
            },
        }
    }

    def test_not_found_unssl(self):
        cfg = self._run_configs["cfg"]
        self._scan(cfg["target"], cfg["plugins"])

        vulns = self.kb.get("un_ssl", "un_ssl")
        self.assertEqual(0, len(vulns))
