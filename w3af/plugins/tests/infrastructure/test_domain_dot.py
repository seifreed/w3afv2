"""
test_domain_dot.py

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
import unittest
from typing import ClassVar

from w3af.core.data.kb.knowledge_base import DBKnowledgeBase
from w3af.core.data.request.fuzzable_request import FuzzableRequest
from w3af.core.data.url.extended_urllib import ExtendedUrllib
from w3af.plugins.infrastructure.domain_dot import domain_dot
from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest
from w3af.plugins.tests.infrastructure.canned_plugin_test import closed_port_url

INDEX = '<html><body><a href="login.php">login</a><a href="news.php">news</a>'
SOURCE = "<?php\n$password = $_POST['password'];\nmysql_connect($db, $user);\n?>"
PAGES = {"/": INDEX, "/login.php": INDEX, "/news.php": INDEX}


def _dotted_domain_shows_source(mock_response, request, uri, headers):
    headers["Content-Type"] = "text/html"
    path = request.path

    if path not in PAGES:
        return 404, headers, "Not found"

    if request.headers["Host"].endswith("."):
        return 200, headers, SOURCE

    return 200, headers, PAGES[path]


class TestDomainDot(PluginTest):

    target_url = "http://domain/"

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(re.compile(".*"), body="<html><body>Same page</body></html>")
    ]

    plugins: ClassVar[dict] = {"infrastructure": (PluginConfig("domain_dot"),)}

    def test_domain_dot(self):
        self._scan(self.target_url, self.plugins)

        infos = self.kb.get("domain_dot", "domain_dot")
        self.assertEqual(len(infos), 0, infos)


class TestDomainDotMisconfiguration(PluginTest):

    target_url = "http://domain/"

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(re.compile(".*"), body=_dotted_domain_shows_source)
    ]

    plugins: ClassVar[dict] = {
        "infrastructure": (PluginConfig("domain_dot"),),
        "crawl": (PluginConfig("web_spider"),),
    }

    def test_virtual_host_misconfiguration(self):
        self._scan(self.target_url, self.plugins)

        infos = self.kb.get("domain_dot", "domain_dot")
        self.assertEqual(len(infos), 2, infos)
        self.assertEqual(
            {i.get_name() for i in infos}, {"Potential virtual host misconfiguration"}
        )

        dotted = [r for r in self.received_requests if r.headers["Host"] == "domain."]
        self.assertEqual(len(dotted), 2, dotted)


class TestDomainDotRequestError(unittest.TestCase):
    def test_error_is_reported(self):
        kb.cleanup()
        plugin = domain_dot()
        plugin.set_knowledge_base(kb)
        plugin._uri_opener = ExtendedUrllib()
        self.addCleanup(plugin._uri_opener.end)

        plugin.discover(FuzzableRequest(closed_port_url()), 1)

        self.assertEqual(kb.get("domain_dot", "domain_dot"), [])
        self.assertIn("trailing dot", plugin.get_long_desc())


kb = DBKnowledgeBase()
