"""
test_directory_indexing.py

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

from w3af.core.data.constants import severity
from w3af.core.data.dc.headers import Headers
from w3af.core.data.kb.knowledge_base import DBKnowledgeBase
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.request.fuzzable_request import FuzzableRequest
from w3af.core.data.url.http_response import HTTPResponse
from w3af.core.filesystem import create_temp_dir
from w3af.plugins.grep.directory_indexing import directory_indexing
from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest

INDEX_BODY = (
    "<html><head><title>Index of /secret</title></head>"
    '<body><h1>Index of /secret</h1><a href="?C=N;O=D">Name</a>'
    '<a href="../">Parent Directory</a></body></html>'
)


class TestDirectoryIndexingIntegration(PluginTest):

    target_url = "http://mock/secret/"

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(url="http://mock/secret/", body=INDEX_BODY, method="GET"),
    ]

    _run_configs: ClassVar[dict] = {
        "cfg1": {
            "target": target_url,
            "plugins": {"grep": (PluginConfig("directory_indexing"),)},
        }
    }

    def test_found_vuln(self):
        cfg = self._run_configs["cfg1"]
        self._scan(cfg["target"], cfg["plugins"])

        vulns = self.kb.get("directory_indexing", "directory")
        self.assertEqual(1, len(vulns))
        v = vulns[0]

        self.assertEqual(self.target_url, str(v.get_url()))
        self.assertEqual(severity.LOW, v.get_severity())
        self.assertEqual("Directory indexing", v.get_name())


class TestDirectoryIndexingUnit(unittest.TestCase):

    def setUp(self):
        create_temp_dir()
        kb.cleanup()
        self.plugin = directory_indexing()
        self.url = URL("http://www.w3af.com/secret/")
        self.request = FuzzableRequest(self.url)

    def tearDown(self):
        self.plugin.end()

    def test_directory_indexing_found(self):
        headers = Headers([("content-type", "text/html")])
        response = HTTPResponse(200, INDEX_BODY, headers, self.url, self.url, _id=1)
        self.plugin.grep(self.request, response)
        self.assertEqual(len(kb.get("directory_indexing", "directory")), 1)

    def test_directory_indexing_not_found(self):
        headers = Headers([("content-type", "text/html")])
        body = "<html><body>regular page</body></html>"
        response = HTTPResponse(200, body, headers, self.url, self.url, _id=1)
        self.plugin.grep(self.request, response)
        self.assertEqual(len(kb.get("directory_indexing", "directory")), 0)

    def test_directory_indexing_not_text(self):
        headers = Headers([("content-type", "image/png")])
        response = HTTPResponse(200, INDEX_BODY, headers, self.url, self.url, _id=1)
        self.plugin.grep(self.request, response)
        self.assertEqual(len(kb.get("directory_indexing", "directory")), 0)

    def test_directory_indexing_visited_once(self):
        headers = Headers([("content-type", "text/html")])
        response = HTTPResponse(200, INDEX_BODY, headers, self.url, self.url, _id=1)
        self.plugin.grep(self.request, response)
        self.plugin.grep(self.request, response)
        self.assertEqual(len(kb.get("directory_indexing", "directory")), 1)


kb = DBKnowledgeBase()
