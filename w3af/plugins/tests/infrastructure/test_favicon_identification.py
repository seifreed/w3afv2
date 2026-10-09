"""
test_favicon_identification.py

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

import hashlib
import os
import unittest
from typing import ClassVar

from w3af.plugins.infrastructure.favicon_identification import (
    favicon_identification,
)
from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest

TARGET = "http://favicon/"
UNKNOWN_FAVICON = b"\x00\x00\x01\x00\x01\x00\x10\x10\xff\xfe w3af"


class FaviconTest(PluginTest):

    target_url = TARGET

    plugins: ClassVar[dict] = {
        "infrastructure": (PluginConfig("favicon_identification"),)
    }

    def scan_infos(self):
        self._scan(self.target_url, self.plugins)
        return self.kb.get("favicon_identification", "info")


class TestKnownFavicon(FaviconTest):

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(TARGET, "<html><body>Home</body></html>"),
        MockResponse(TARGET + "favicon.ico", b"", content_type="image/x-icon"),
    ]

    def test_favicon_identification(self):
        infos = self.scan_infos()

        self.assertEqual(len(infos), 1, infos)
        self.assertEqual(infos[0].get_name(), "Favicon identification")
        self.assertIn("Zero byte favicon", infos[0].get_desc())
        self.assertEqual(infos[0].get_url().url_string, TARGET + "favicon.ico")


class TestUnknownFavicon(FaviconTest):

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(TARGET, "<html><body>Home</body></html>"),
        MockResponse(
            TARGET + "favicon.ico", UNKNOWN_FAVICON, content_type="image/x-icon"
        ),
    ]

    def test_favicon_identification_failed(self):
        infos = self.scan_infos()

        self.assertEqual(len(infos), 1, infos)
        self.assertEqual(infos[0].get_name(), "Favicon identification failed")

        md5 = hashlib.md5(UNKNOWN_FAVICON, usedforsecurity=False).hexdigest()
        self.assertIn(md5, infos[0].get_desc())


class TestTextFavicon(FaviconTest):

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(TARGET, "<html><body>Home</body></html>"),
        MockResponse(TARGET + "favicon.ico", "not an icon", content_type="text/plain"),
    ]

    def test_text_body_is_hashed(self):
        infos = self.scan_infos()

        md5 = hashlib.md5(b"not an icon", usedforsecurity=False).hexdigest()
        self.assertEqual(len(infos), 1, infos)
        self.assertIn(md5, infos[0].get_desc())


class TestNoFavicon(FaviconTest):

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(TARGET, "<html><body>Home</body></html>"),
    ]

    def test_no_favicon_identification(self):
        self.assertEqual(self.scan_infos(), [])


class TestFaviconDatabase(unittest.TestCase):
    def test_missing_database(self):
        plugin = favicon_identification()
        plugin._db_file = os.path.join(os.path.dirname(__file__), "missing-md5-db")

        self.assertEqual(list(plugin._read_favicon_db()), [])

    def test_long_description(self):
        self.assertIn("favicon", favicon_identification().get_long_desc())
