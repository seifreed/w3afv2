"""
test_frontpage_version.py

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

import unittest
from typing import ClassVar

from w3af.plugins.infrastructure.frontpage_version import frontpage_version
from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest


class TestFrontpageVersion(PluginTest):

    target_url = "http://httpretty"

    FRONTPAGE_BODY = (
        'FPVersion="1.2.3"\n'
        'FPAdminScriptUrl="/admin"\n'
        'FPAuthorScriptUrl="/author"\n'
    )

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(
            "http://httpretty/_vti_inf.html",
            body=FRONTPAGE_BODY,
            method="GET",
            status=200,
        )
    ]

    _run_configs: ClassVar[dict] = {
        "cfg": {
            "target": target_url,
            "plugins": {"infrastructure": (PluginConfig("frontpage_version"),)},
        }
    }

    def test_find_version(self):
        cfg = self._run_configs["cfg"]
        self._scan(cfg["target"], cfg["plugins"])

        infos = self.kb.get("frontpage_version", "frontpage_version")

        EXPECTED = ("/_vti_inf.html", "/author", "/admin")

        self.assertEqual(len(infos), len(EXPECTED), infos)

        self.assertEqual(
            {self.target_url + path_file for path_file in EXPECTED},
            {i.get_url().url_string for i in infos},
        )


class TestFrontpageVersionDefaultLocations(PluginTest):

    target_url = "http://httpretty/site/index.html"

    DEFAULT_BODY = (
        'FPVersion="5.0.2.6790"\n'
        'FPAdminScriptUrl="_vti_bin/_vti_adm/admin.exe"\n'
        'FPAuthorScriptUrl="_vti_bin/_vti_aut/author.exe"\n'
    )

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse("http://httpretty/site/index.html", "Index"),
        MockResponse("http://httpretty/_vti_inf.html", "<html>Maintenance</html>"),
        MockResponse("http://httpretty/site/_vti_inf.html", DEFAULT_BODY),
    ]

    def test_default_script_locations(self):
        plugins = {"infrastructure": (PluginConfig("frontpage_version"),)}
        self._scan(self.target_url, plugins)

        infos = self.kb.get("frontpage_version", "frontpage_version")

        self.assertEqual(
            {(i.get_name(), i.get_url().get_path()) for i in infos},
            {
                ("FrontPage configuration information", "/site/_vti_inf.html"),
                ("FrontPage FPAdminScriptUrl", "/site/_vti_bin/_vti_adm/admin.exe"),
                ("FrontPage FPAuthorScriptUrl", "/site/_vti_bin/_vti_aut/author.exe"),
            },
        )


class TestFrontpageVersionDescription(unittest.TestCase):
    def test_long_desc_names_the_info_file(self):
        self.assertIn("_vti_inf.html", frontpage_version().get_long_desc())
