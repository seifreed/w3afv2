"""
test_server_header.py

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

from w3af.core.data.dc.headers import Headers
from w3af.core.data.kb.knowledge_base import DBKnowledgeBase
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.url.helpers import new_no_content_resp
from w3af.core.data.url.http_response import HTTPResponse
from w3af.plugins.infrastructure.server_header import server_header
from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest

SERVER = "Apache/2.4.58 (Ubuntu)"
POWERED_BY = "PHP/8.3.6-0ubuntu0.24.04.1"


class TestServerHeader(PluginTest):

    target_url = "http://mock/"

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(
            target_url,
            "<html><body>Hello</body></html>",
            headers={"Server": SERVER, "X-Powered-By": POWERED_BY},
        )
    ]

    def test_find_server_power(self):
        plugins = {"infrastructure": (PluginConfig("server_header"),)}
        self._scan(self.target_url, plugins)

        server = self.kb.get("server_header", "server")
        pow_by = self.kb.get("server_header", "powered_by")
        pow_by_str_lst = self.kb.raw_read("server_header", "powered_by_string")

        self.assertEqual(len(server), 1, server)
        self.assertEqual(len(pow_by), 1, pow_by)

        self.assertEqual(server[0].get_name(), "Server header")
        self.assertEqual(server[0]["server"], SERVER)
        self.assertEqual(self.kb.raw_read("server_header", "server_string"), SERVER)
        self.assertEqual(pow_by[0].get_name(), "Powered-by header")

        self.assertEqual(pow_by_str_lst, [POWERED_BY])


class TestOmittedServerHeader(PluginTest):

    target_url = "http://mock/"

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(
            target_url, "<html><body>Hello</body></html>", headers={"Server": None}
        )
    ]

    def test_omitted_server_header(self):
        plugins = {"infrastructure": (PluginConfig("server_header"),)}
        self._scan(self.target_url, plugins)

        omitted = self.kb.get("server_header", "omitted_server_header")

        self.assertEqual(len(omitted), 1, omitted)
        self.assertEqual(omitted[0].get_name(), "Omitted server header")
        self.assertEqual(self.kb.get("server_header", "server"), [])
        self.assertEqual(self.kb.raw_read("server_header", "server_string"), "")


class TestServerHeaderAnalysis(unittest.TestCase):
    """
    Analyze responses directly, which is the only way to feed the plugin the
    generated 204 response that replaces failed requests and to analyze the
    same headers more than once.
    """

    def setUp(self):
        kb.cleanup()
        self.addCleanup(kb.cleanup)
        self.plugin = server_header()
        self.plugin.set_knowledge_base(kb)

    def test_no_content_response_is_ignored(self):
        response = new_no_content_resp(URL("http://mock/"))

        self.plugin._check_server_header(None, response)

        self.assertEqual(kb.get("server_header", "server"), [])
        self.assertEqual(kb.get("server_header", "omitted_server_header"), [])

    def test_repeated_headers_are_reported_once(self):
        url = URL("http://mock/")
        headers = Headers([("Server", SERVER), ("X-AspNet-Version", "4.0.30319")])
        response = HTTPResponse(200, "Hello", headers, url, url, _id=1)

        for _ in range(2):
            self.plugin._check_server_header(None, response)
            self.plugin._check_x_power(None, response)

        self.assertEqual(len(kb.get("server_header", "server")), 1)
        self.assertEqual(len(kb.get("server_header", "powered_by")), 1)

    def test_long_desc_mentions_hmap(self):
        self.assertIn("hmap", self.plugin.get_long_desc())


kb = DBKnowledgeBase()
