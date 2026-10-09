"""
test_ria_enumerator.py

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

import os
import tempfile
import unittest
from typing import ClassVar

from w3af.plugins.crawl.ria_enumerator import ria_enumerator
from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest

TARGET_URL = "http://mock/"

CROSSDOMAIN = """<?xml version="1.0"?>
<cross-domain-policy>
  <allow-access-from domain="*" />
  <allow-access-from domain="partner.example.com" />
</cross-domain-policy>
"""

BROKEN_CLIENT_ACCESS_POLICY = "<access-policy><cross-domain-access><policy>"

GEARS_MANIFEST = '{"betaManifestVersion": 1, "version": "1", "entries": []}'

RUN_CONFIG: dict = {
    "crawl": (
        PluginConfig(
            "ria_enumerator",
            ("manifestExtensions", ".json", PluginConfig.LIST),
        ),
    )
}


class TestRIAEnumerator(PluginTest):

    target_url = TARGET_URL

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(TARGET_URL, "index"),
        MockResponse(TARGET_URL + "crossdomain.xml", CROSSDOMAIN, "text/xml"),
        MockResponse(
            TARGET_URL + "clientaccesspolicy.xml",
            BROKEN_CLIENT_ACCESS_POLICY,
            "text/xml",
        ),
        MockResponse(TARGET_URL + "manifest.json", GEARS_MANIFEST, "application/json"),
    ]

    def test_ria_enumerator(self):
        self._scan(self.target_url, RUN_CONFIG)

        infos = self.kb.get("ria_enumerator", "info")
        self.assertEqual(
            sorted(i.get_name() for i in infos),
            ["Cross-domain allow ACL", "Invalid RIA settings file"],
        )

        urls = {i.get_url().url_string for i in infos}
        self.assertEqual(
            urls,
            {TARGET_URL + "crossdomain.xml", TARGET_URL + "clientaccesspolicy.xml"},
        )

        vulns = self.kb.get("ria_enumerator", "vuln")
        self.assertEqual(len(vulns), 1, vulns)
        self.assertEqual(vulns[0].get_name(), "Insecure RIA settings")

        gears = self.kb.get("ria_enumerator", "gears_manifest")
        self.assertEqual(
            [g.get_url().url_string for g in gears], [TARGET_URL + "manifest.json"]
        )


class TestRIAEnumeratorInvalidXML(PluginTest):

    target_url = TARGET_URL

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(TARGET_URL, "index"),
        MockResponse(TARGET_URL + "crossdomain.xml", "<not><valid>", "text/xml"),
    ]

    def test_invalid_xml_without_policy_keywords_is_ignored(self):
        self._scan(self.target_url, RUN_CONFIG)

        self.assertEqual(self.kb.get_all_findings(), [])


class TestRIAEnumeratorOptions(unittest.TestCase):

    def test_set_options(self):
        plugin = ria_enumerator()

        with tempfile.NamedTemporaryFile("w", suffix=".db", delete=False) as wordlist:
            wordlist.write("manifest\n")
        self.addCleanup(os.remove, wordlist.name)

        options = plugin.get_options()
        options["wordlist"].set_value(wordlist.name)
        options["manifestExtensions"].set_value(".txt")
        plugin.set_options(options)

        self.assertEqual(plugin.get_options()["wordlist"].get_value(), wordlist.name)
        self.assertEqual(
            plugin.get_options()["manifestExtensions"].get_value(), [".txt"]
        )

    def test_missing_wordlist_keeps_default(self):
        plugin = ria_enumerator()
        default_wordlist = plugin.get_options()["wordlist"].get_value()

        options = plugin.get_options()
        options["wordlist"].set_value("/does/not/exist.db")
        plugin.set_options(options)

        self.assertEqual(plugin.get_options()["wordlist"].get_value(), default_wordlist)

    def test_long_desc(self):
        self.assertIn("crossdomain.xml", ria_enumerator().get_long_desc())
