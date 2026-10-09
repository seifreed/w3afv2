"""
test_dir_file_bruter.py

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
from typing import ClassVar

from w3af import ROOT_PATH
from w3af.core.data.parsers.doc.url import URL
from w3af.plugins.crawl.dir_file_bruter import dir_file_bruter
from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest

SITE_URL = "http://mock/"

EXISTING_PATHS = (
    "",
    "crawl/",
    "portal/",
    "iamhidden.txt",
    "crawl/dir_bruter/",
    "crawl/dir_bruter/hidden-inside-dir.txt",
    "crawl/dir_bruter/spameggs/",
    "crawl/dir_bruter/spameggs/foobar/",
)


class TestDirFileBruter(PluginTest):

    TEST_PATH = os.path.join(ROOT_PATH, "plugins", "tests", "crawl", "dir_file_bruter")

    DIR_DB_PATH = os.path.join(TEST_PATH, "test_dirs_small.db")
    FILE_DB_PATH = os.path.join(TEST_PATH, "test_files_small.db")

    directory_url = SITE_URL + "crawl/dir_bruter/"
    base_url = SITE_URL
    target_url = SITE_URL

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(SITE_URL + path, f"<html>Content of /{path}</html>")
        for path in EXISTING_PATHS
    ]

    _run_directories: ClassVar[dict] = {
        "target": base_url,
        "plugins": {
            "crawl": (
                PluginConfig(
                    "dir_file_bruter",
                    ("dir_wordlist", DIR_DB_PATH, PluginConfig.INPUT_FILE),
                ),
            )
        },
    }

    _run_files: ClassVar[dict] = {
        "target": base_url,
        "plugins": {
            "crawl": (
                PluginConfig(
                    "dir_file_bruter",
                    ("file_wordlist", FILE_DB_PATH, PluginConfig.INPUT_FILE),
                    ("bf_files", True, PluginConfig.BOOL),
                    ("bf_directories", False, PluginConfig.BOOL),
                ),
            )
        },
    }

    _run_directory_files: ClassVar[dict] = {
        "target": directory_url,
        "plugins": {
            "crawl": (
                PluginConfig(
                    "dir_file_bruter",
                    ("dir_wordlist", DIR_DB_PATH, PluginConfig.INPUT_FILE),
                    ("bf_directories", True, PluginConfig.BOOL),
                    ("file_wordlist", FILE_DB_PATH, PluginConfig.INPUT_FILE),
                    ("bf_files", True, PluginConfig.BOOL),
                ),
            )
        },
    }

    _run_recursive: ClassVar[dict] = {
        "target": directory_url,
        "plugins": {
            "crawl": (
                PluginConfig(
                    "dir_file_bruter",
                    ("dir_wordlist", DIR_DB_PATH, PluginConfig.INPUT_FILE),
                    ("bf_directories", True, PluginConfig.BOOL),
                    ("file_wordlist", FILE_DB_PATH, PluginConfig.INPUT_FILE),
                    ("bf_files", True, PluginConfig.BOOL),
                    ("be_recursive", True, PluginConfig.BOOL),
                ),
            )
        },
    }

    def test_directories(self):
        self._scan(self._run_directories["target"], self._run_directories["plugins"])

        expected_urls = ("/crawl/", "/portal/", "/")
        self.assertAllURLsFound(expected_urls)

    def test_files(self):
        self._scan(self._run_files["target"], self._run_files["plugins"])

        expected_urls = ("/iamhidden.txt", "/")
        self.assertAllURLsFound(expected_urls)

    def test_directories_files(self):
        self._scan(
            self._run_directory_files["target"], self._run_directory_files["plugins"]
        )

        expected_urls = (
            "/crawl/dir_bruter/",
            "/crawl/dir_bruter/hidden-inside-dir.txt",
            "/crawl/dir_bruter/spameggs/",
        )
        self.assertAllURLsFound(expected_urls)

    def test_recursive(self):
        self._scan(self._run_recursive["target"], self._run_recursive["plugins"])

        expected_urls = (
            "/crawl/dir_bruter/",
            "/crawl/dir_bruter/hidden-inside-dir.txt",
            "/crawl/dir_bruter/spameggs/foobar/",
            "/crawl/dir_bruter/spameggs/",
        )
        self.assertAllURLsFound(expected_urls)

    def test_wordlist_skips_comments_blank_and_invalid_lines(self):
        with tempfile.NamedTemporaryFile("w", suffix=".db", delete=False) as wordlist:
            wordlist.write("# comment\n\n//[\nadmin\n")
        self.addCleanup(os.remove, wordlist.name)

        plugin = dir_file_bruter()
        generated = list(
            plugin._read_db_file_gen_url(URL(SITE_URL), wordlist.name, True)
        )
        plugin.end()

        self.assertEqual(generated, [("admin/", URL(SITE_URL + "admin/"))])

    def test_long_description(self):
        self.assertIn("brute-forcing", dir_file_bruter().get_long_desc())
