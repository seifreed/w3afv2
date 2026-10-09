# -*- coding: UTF-8 -*-
"""
test_javascript.py

Copyright 2014 Andres Riancho

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
from pathlib import Path

from w3af import ROOT_PATH
from w3af.core.data.dc.headers import Headers
from w3af.core.data.parsers.doc.javascript import JavaScriptParser
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.url.http_response import HTTPResponse


class TestJavaScriptParser(unittest.TestCase):

    DATA_PATH = Path(
        ROOT_PATH, "core", "data", "parsers", "doc", "tests", "data", "javascript"
    )

    def parse(self, filename):
        return self.parse_body(Path(self.DATA_PATH, filename).read_text())

    def parse_body(self, body, js_mime="text/javascript"):
        hdrs = Headers([("Content-Type", js_mime)])
        response = HTTPResponse(
            200, body, hdrs, URL("http://moth/xyz/"), URL("http://moth/xyz/"), _id=1
        )

        parser = JavaScriptParser(response)
        parser.parse()
        return parser

    def test_false_positives(self):
        for filename in (
            "jquery.js",
            "angular.js",
            "test_1.js",
            "test_2.js",
            "test_3.js",
        ):
            p = self.parse(filename)
            self.assertEqual(p.get_references(), ([], []))

    def assert_spam_and_eggs(self, parser):
        parsed, re_refs = parser.get_references()

        self.assertEqual(parsed, [])
        self.assertEqual(
            set(re_refs), {URL("http://moth/spam.html"), URL("http://moth/eggs.html")}
        )

    def test_relative(self):
        self.assert_spam_and_eggs(self.parse("test_4.js"))

    def test_full(self):
        self.assert_spam_and_eggs(self.parse("test_full_url.js"))

    def test_can_parse(self):
        for mime in ("application/javascript", "text/ecmascript", "text/jscript"):
            response = self.parse_body("", mime).get_http_response()
            self.assertTrue(JavaScriptParser.can_parse(response))

        response = self.parse_body("", "text/html").get_http_response()
        self.assertFalse(JavaScriptParser.can_parse(response))

    def test_clear_text_body_is_the_whole_body(self):
        parser = self.parse_body("var a = 1;")

        self.assertEqual(parser.get_clear_text_body(), "var a = 1;")
        self.assertEqual(parser.get_forms(), [])
        self.assertEqual(parser.get_emails(), [])
