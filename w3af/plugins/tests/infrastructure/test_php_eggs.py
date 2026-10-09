"""
test_php_eggs.py

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

import json
import os
import tempfile
from typing import ClassVar

import pytest

from w3af.plugins.infrastructure.php_eggs import md5_hash
from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest

EGG_HASHES = {
    "credits": md5_hash("1"),
    "php_1": md5_hash("2"),
    "php_2": md5_hash("3"),
    "zend": md5_hash("4"),
}


@pytest.mark.smoke
class TestPHPEggs(PluginTest):

    target_url = "http://mock/"
    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse("http://mock/?=PHPB8B5F2A0-3C92-11d3-A3A9-4C7B08C10000", "1"),
        MockResponse(
            "http://mock/?=PHPE9568F34-D428-11d2-A769-00AA001ACF42",
            "2",
            content_type="image/png",
        ),
        MockResponse(
            "http://mock/?=PHPE9568F35-D428-11d2-A769-00AA001ACF42",
            "3",
            content_type="image/png",
        ),
        MockResponse(
            "http://mock/?=PHPE9568F36-D428-11d2-A769-00AA001ACF42",
            "4",
            content_type="image/png",
        ),
    ]

    def _write_eggs_db(self):
        """
        :return: The path to an eggs database where the bodies served by the
                 canned server identify PHP 5.3.2 and 5.3.1
        """
        eggs_db = {
            "db": [
                {"version": "5.3.2", **EGG_HASHES},
                {"version": "5.3.1", **EGG_HASHES},
                {"version": "5.2.0", **EGG_HASHES, "credits": md5_hash("other")},
            ]
        }
        file_descriptor, path = tempfile.mkstemp(suffix=".json")
        with os.fdopen(file_descriptor, "w") as eggs_db_file:
            json.dump(eggs_db, eggs_db_file)
        self.addCleanup(os.unlink, path)
        return path

    def test_php_eggs_fingerprinted(self):
        eggs_db_path = self._write_eggs_db()
        plugins = {
            "infrastructure": (
                PluginConfig(
                    "php_eggs", ("eggs_db", eggs_db_path, PluginConfig.INPUT_FILE)
                ),
            )
        }

        self._scan(self.target_url, plugins)

        eggs = self.kb.get("php_eggs", "eggs")
        self.assertEqual(len(eggs), 4, eggs)

        for egg in eggs:
            self.assertIn("PHP Egg", egg.get_name())

        php_version = self.kb.get("php_eggs", "version")
        self.assertEqual(len(php_version), 1, php_version)

        php_version = php_version[0]
        self.assertEqual(php_version["version"], ["5.3.2", "5.3.1"])


@pytest.mark.smoke
class TestPHPEggsNoFingerprint(PluginTest):

    target_url = "http://mock/"
    MOCK_RESPONSES: ClassVar[list] = [MockResponse(target_url, "Index is not empty")]

    _run_configs: ClassVar[dict] = {
        "cfg": {
            "target": None,
            "plugins": {"infrastructure": (PluginConfig("php_eggs"),)},
        }
    }

    def test_php_eggs_fingerprinted(self):
        cfg = self._run_configs["cfg"]

        self._scan(self.target_url, cfg["plugins"])

        eggs = self.kb.get("php_eggs", "eggs")
        php_version = self.kb.get("php_eggs", "version")

        self.assertEqual(len(eggs), 0, eggs)
        self.assertEqual(len(php_version), 0, php_version)
