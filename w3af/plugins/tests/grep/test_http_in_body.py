"""
test_http_in_body.py

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

import w3af.core.data.kb.knowledge_base as kb
from w3af.core.data.constants import severity
from w3af.core.data.dc.headers import Headers
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.request.fuzzable_request import FuzzableRequest
from w3af.core.data.url.http_response import HTTPResponse
from w3af.core.filesystem import create_temp_dir
from w3af.plugins.grep.http_in_body import http_in_body


class TestHttpInBody(unittest.TestCase):

    def setUp(self):
        create_temp_dir()
        kb.kb.cleanup()
        self.plugin = http_in_body()
        self.plugin.set_knowledge_base(kb.kb)
        self.url = URL("http://www.w3af.com/")
        self.request = FuzzableRequest(self.url)

    def tearDown(self):
        self.plugin.end()

    def _grep(self, body, code=200, content_type="text/html"):
        headers = Headers([("content-type", content_type)])
        response = HTTPResponse(code, body, headers, self.url, self.url, _id=1)
        self.plugin.grep(self.request, response)

    def test_found_request(self):
        self._grep("A debug trace: GET /index.html HTTP/1.0 was logged here")

        infos = kb.kb.get("http_in_body", "request")
        self.assertEqual(1, len(infos), infos)
        info = infos[0]
        self.assertEqual(severity.INFORMATION, info.get_severity())
        self.assertEqual("HTTP Request in HTTP body", info.get_name())

    def test_found_response(self):
        self._grep("The upstream said HTTP/1.1 200 OK in the body")

        infos = kb.kb.get("http_in_body", "response")
        self.assertEqual(1, len(infos), infos)
        info = infos[0]
        self.assertEqual("HTTP Response in HTTP body", info.get_name())

    def test_no_http_in_body(self):
        self._grep("<html><body>regular content</body></html>")
        self.assertEqual(0, len(kb.kb.get("http_in_body", "request")))
        self.assertEqual(0, len(kb.kb.get("http_in_body", "response")))

    def test_501_is_skipped(self):
        self._grep("<h2>HTTP/1.1 501 Not Implemented</h2>", code=501)
        self.assertEqual(0, len(kb.kb.get("http_in_body", "response")))

    def test_not_text(self):
        self._grep("GET /index.html HTTP/1.0", content_type="image/png")
        self.assertEqual(0, len(kb.kb.get("http_in_body", "request")))

    def test_end_reporting(self):
        self._grep("A debug trace: GET /index.html HTTP/1.0 was logged here")
        self.plugin.end()
        self.assertEqual(1, len(kb.kb.get("http_in_body", "request")))
