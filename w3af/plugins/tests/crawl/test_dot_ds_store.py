"""
test_ds_store.py

Copyright 2018 Andres Riancho

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
from pathlib import Path
from typing import Any, ClassVar, cast

from ds_store import DSStore

from w3af import ROOT_PATH
from w3af.core.data.db.dbms import get_default_temp_db_instance
from w3af.plugins.crawl.dot_ds_store import DsStore, dot_ds_store
from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest

RUN_PLUGINS = {"crawl": (PluginConfig("dot_ds_store"),)}


def build_ds_store(*filenames):
    with tempfile.TemporaryDirectory() as temp_dir:
        path = os.path.join(temp_dir, "DS_Store")
        store = cast(Any, DSStore.open(path, "w+"))
        for filename in filenames:
            store[filename]["Iloc"] = (10, 20)
        store.close()
        return Path(path).read_bytes()


class TestDSStore(PluginTest):

    target_url = "http://mock"

    _run_configs: ClassVar[dict] = {
        "cfg": {
            "target": target_url,
            "plugins": {"crawl": (PluginConfig("dot_ds_store"),)},
        }
    }

    DS_STORE = Path(
        os.path.join(ROOT_PATH, "plugins/tests/crawl/ds_store/DS_Store")
    ).read_bytes()

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse("http://mock/.DS_Store", DS_STORE),
        MockResponse("http://mock/other", "Secret directory"),
        MockResponse("http://mock/", "Not here", status=404),
    ]

    def test_ds_store(self):
        cfg = self._run_configs["cfg"]
        self._scan(cfg["target"], cfg["plugins"])

        infos = self.kb.get("dot_ds_store", "dot_ds_store")
        self.assertEqual(len(infos), 1, infos)

        info = infos[0]
        self.assertEqual(info.get_name(), ".DS_Store file found")

        expected_urls = ("/", "/.DS_Store", "/other")
        urls = self.kb.get_all_known_urls()

        self.assertEqual(
            {str(u) for u in urls},
            {(self.target_url + end) for end in expected_urls},
        )


class TestInvalidDSStore(PluginTest):

    target_url = "http://mock/dir/"

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse("http://mock/dir/.DS_Store", b"This is not a DS_Store file"),
        MockResponse("http://mock/dir/", "Directory index"),
    ]

    def test_invalid_ds_store_is_ignored(self):
        self._scan(self.target_url, RUN_PLUGINS)

        self.assertEqual(self.kb.get("dot_ds_store", "dot_ds_store"), [])

        requested_paths = {request.path for request in self.received_requests}
        self.assertIn("/.DS_Store", requested_paths)


class TestDsStoreParser(unittest.TestCase):
    def test_current_and_parent_directories_are_skipped(self):
        store = DsStore(build_ds_store(".", "..", "secret.txt"))

        self.assertEqual(store.get_file_entries(), {"secret.txt"})

    def test_long_description(self):
        plugin = dot_ds_store(db=get_default_temp_db_instance())
        self.assertIn(".DS_Store", plugin.get_long_desc())
