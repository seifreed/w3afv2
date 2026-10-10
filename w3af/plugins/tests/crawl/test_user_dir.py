"""
test_user_dir.py

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

import csv
from typing import ClassVar

import pytest

import w3af.core.controllers.output_manager as om
from w3af.core.data.kb.info import Info
from w3af.plugins.crawl.user_db.user_db import APPLICATION, OS, get_users_from_csv
from w3af.plugins.crawl.user_dir import user_dir
from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest


class TestUserDir(PluginTest):

    target_url = "http://httpretty/"

    _run_configs: ClassVar[dict] = {
        "cfg": {"target": target_url, "plugins": {"crawl": (PluginConfig("user_dir"),)}}
    }

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse("http://httpretty/~www/", "www user home directory."),
        MockResponse("http://httpretty/www/", "www user home directory.", delay=1),
        MockResponse("http://httpretty/~jdoe/", "jdoe user home directory."),
        MockResponse("http://httpretty/~kmem/", "kmem user home directory."),
        MockResponse("http://httpretty//xfs/", "home sweet home"),
    ]

    EXPECTED_RESULTS: ClassVar[set] = {
        ("Web user home directory", "http://httpretty/~www/"),
        ("Web user home directory", "http://httpretty/~kmem/"),
        ("Web user home directory", "http://httpretty/~jdoe/"),
        ("Web user home directory", "http://httpretty/xfs/"),
        ("Identified installed application", "http://httpretty/xfs/"),
        ("Fingerprinted operating system", "http://httpretty/~kmem/"),
    }

    def test_fuzzer_user(self):
        # The finger_* dependencies query search engines through the canned
        # HTTP server, which knows no users, so only the internal user list
        # is used by user_dir
        email = Info(
            "Email address", "The jdoe@httpretty email address was found.", 1, "emails"
        )
        email["user"] = "jdoe"
        self.kb.append("emails", "emails", email)

        cfg = self._run_configs["cfg"]
        self._scan(cfg["target"], cfg["plugins"])

        users = self.kb.get("user_dir", "users")
        scan_results = {(i.get_name(), i.get_url().url_string) for i in users}

        self.assertEqual(self.EXPECTED_RESULTS, scan_results)


def test_user_dir_long_desc():
    if "home directories" not in user_dir().get_long_desc():
        raise AssertionError


def test_users_from_csv_reads_bundled_database():
    users = list(get_users_from_csv(OS, om.out))

    if not users:
        raise AssertionError
    if not all(isinstance(user, str) for _, user in users):
        raise AssertionError


def test_users_from_csv_rejects_unknown_database():
    with pytest.raises(ValueError, match="Invalid identification"):
        list(get_users_from_csv("unknown", om.out))


def test_users_from_csv_skips_invalid_rows(tmp_path):
    oversized_field = "x" * (csv.field_size_limit() + 1)
    (tmp_path / f"{APPLICATION}.csv").write_text(
        "\n".join(
            [
                "# a comment line",
                "",
                "a row with a single field",
                f'"{oversized_field}",user',
                "Apache web server,www",
            ]
        ),
        encoding="utf-8",
    )

    users = list(get_users_from_csv(APPLICATION, om.out, db_path=tmp_path))

    if users != [("Apache web server", "www")]:
        raise AssertionError
