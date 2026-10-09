"""
test_server_status.py

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

from w3af.plugins.infrastructure.server_status import server_status
from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest


def _scoreboard_row(vhost, request_line):
    return (
        "<tr><td><b>0-0</b></td><td>1234</td><td>0/1/1</td><td>_</td>"
        f"<td>127.0.0.1</td><td nowrap>{vhost}</td>"
        f"<td nowrap>{request_line}</td></tr>"
    )


SERVER_STATUS_PAGE = "\n".join(
    [
        "<html><head><title>Apache Status</title></head><body>",
        "<h1>Apache Server Status for httpretty-mock</h1>",
        "<dl><dt>Server Version: Apache/2.2.9 (Unix)</dt>",
        "<dt>Server MPM: prefork</dt></dl>",
        "<table border=0>",
        _scoreboard_row("httpretty-mock", "GET /found.php HTTP/1.1"),
        _scoreboard_row("httpretty-mock", "GET /missing.php HTTP/1.1"),
        _scoreboard_row("unavailable", "GET /other.php HTTP/1.1"),
        _scoreboard_row("shared.example.com", "GET /index.php HTTP/1.1"),
        "</table></body></html>",
    ]
)


class TestServerStatus(PluginTest):

    target_url = "http://httpretty-mock/"

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse("http://httpretty-mock/server-status", SERVER_STATUS_PAGE),
        MockResponse("http://httpretty-mock/found.php", "Found page"),
        MockResponse("http://httpretty-mock/other.php", "Other page"),
    ]

    _run_configs: ClassVar[dict] = {
        "cfg": {
            "target": target_url,
            "plugins": {"infrastructure": (PluginConfig("server_status"),)},
        }
    }

    def test_find_server(self):
        cfg = self._run_configs["cfg"]
        self._scan(cfg["target"], cfg["plugins"])

        server = self.kb.get("server_status", "server")

        self.assertEqual(len(server), 1, server)
        self.assertTrue(
            'remote server version: "Apache/2.' in server[0].get_desc(),
            server[0].get_desc(),
        )

    def test_find_urls_and_shared_hosting(self):
        cfg = self._run_configs["cfg"]
        self._scan(cfg["target"], cfg["plugins"])

        known_paths = {url.get_path() for url in self.kb.get_all_known_urls()}
        self.assertIn("/found.php", known_paths)
        self.assertIn("/other.php", known_paths)
        self.assertIn("/server-status", known_paths)
        self.assertNotIn("/missing.php", known_paths)

        shared_hosting = self.kb.get("server_status", "shared_hosting")
        self.assertEqual(len(shared_hosting), 1, shared_hosting)
        self.assertEqual(shared_hosting[0]["also_in_hosting"], ["shared.example.com"])


class TestServerStatusDescription(unittest.TestCase):
    def test_long_desc_mentions_server_status(self):
        self.assertIn("server-status", server_status().get_long_desc())
