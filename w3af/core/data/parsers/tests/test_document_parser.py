# -*- coding: UTF-8 -*-
"""
test_sgml.py

Copyright 2011 Andres Riancho

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
import unittest
from pathlib import Path

from w3af import ROOT_PATH
from w3af.core.data.dc.headers import Headers
from w3af.core.data.parsers.doc.html import HTMLParser
from w3af.core.data.parsers.doc.pdf import PDFParser
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.parsers.document_parser import DocumentParser, url_sort_key
from w3af.core.data.url.http_response import HTTPResponse
from w3af.core.exceptions import BaseFrameworkException


def _build_http_response(body_content, content_type):
    headers = Headers()
    headers["content-type"] = content_type

    url = URL("http://w3af.com")

    return HTTPResponse(200, body_content, headers, url, url, charset="utf-8")


class TestDocumentParserFactory(unittest.TestCase):

    PDF_FILE = os.path.join(
        ROOT_PATH, "core", "data", "parsers", "doc", "tests", "data", "links.pdf"
    )

    HTML_FILE = os.path.join(
        ROOT_PATH,
        "core",
        "data",
        "parsers",
        "doc",
        "tests",
        "data",
        "sharepoint-pl.html",
    )

    def test_html_ok(self):
        mime_types = ["text/html", "TEXT/HTML", "TEXT/plain", "application/xhtml+xml"]

        for mtype in mime_types:
            parser = DocumentParser(_build_http_response("body", mtype))

            self.assertIsInstance(parser, DocumentParser)
            self.assertIsInstance(parser._parser, HTMLParser)
            self.assertEqual(parser.get_clear_text_body(), "body")

    def test_html_upper(self):
        parser = DocumentParser(_build_http_response("", "TEXT/HTML"))

        self.assertIsInstance(parser, DocumentParser)
        self.assertIsInstance(parser._parser, HTMLParser)

    def test_pdf_case01(self):
        parser = DocumentParser(
            _build_http_response(Path(self.PDF_FILE).read_bytes(), "application/pdf")
        )

        self.assertIsInstance(parser, DocumentParser)
        self.assertIsInstance(parser._parser, PDFParser)

    def test_no_parser(self):
        mime_types = ["application/bar", "application/zip", "video/abc", "image/jpeg"]

        for mtype in mime_types:
            response = _build_http_response("body", mtype)
            self.assertRaises(BaseFrameworkException, DocumentParser, response)

    def test_no_parser_binary(self):
        all_chars = "".join([chr(i) for i in range(255)])
        response = _build_http_response(all_chars, "application/bar")
        self.assertRaises(BaseFrameworkException, DocumentParser, response)

    def test_issue_106_invalid_url(self):
        """
        Issue to verify https://github.com/andresriancho/w3af/issues/106
        """
        sharepoint_pl = Path(self.HTML_FILE).read_bytes()
        parser = DocumentParser(_build_http_response(sharepoint_pl, "text/html"))

        self.assertIsInstance(parser, DocumentParser)
        self.assertIsInstance(parser._parser, HTMLParser)

        paths: list[str] = []
        paths.extend(url.get_path_qs() for url in parser.get_references()[0])
        paths.extend(url.get_path_qs() for url in parser.get_references()[1])

        expected_paths = {
            "/szukaj/_vti_bin/search.asmx",
            "/_vti_bin/search.asmx?disco=",
        }

        self.assertEqual(expected_paths, set(paths))


class TestDocumentParserDelegation(unittest.TestCase):

    BODY = (
        "<html><head>"
        '<meta http-equiv="refresh" content="0;url=http://w3af.com/next">'
        '<meta name="author" content="w3af">'
        "</head><body>"
        "<!-- hidden note -->"
        '<a href="/b">b</a><a href="/a">a</a>'
        '<img src="/logo.png">'
        '<form action="/login" method="post"><input name="user"></form>'
        '<a href="mailto:admin@w3af.com">mail us</a>'
        "</body></html>"
    )

    def setUp(self):
        self.response = _build_http_response(self.BODY, "text/html")
        self.parser = DocumentParser(self.response)

    def test_get_references_sorted(self):
        parsed, re_refs = self.parser.get_references()

        self.assertEqual(
            [u.url_string for u in parsed],
            sorted(u.url_string for u in parsed),
        )
        self.assertIn(URL("http://w3af.com/a"), parsed)
        self.assertIsInstance(re_refs, list)

    def test_get_forms(self):
        forms = self.parser.get_forms()

        self.assertEqual(len(forms), 1)
        self.assertEqual(forms[0].get_action(), URL("http://w3af.com/login"))

    def test_get_references_of_tag(self):
        self.assertEqual(
            self.parser.get_references_of_tag("img"), [URL("http://w3af.com/logo.png")]
        )

    def test_get_emails(self):
        self.assertEqual(set(self.parser.get_emails()), {"admin@w3af.com"})
        self.assertEqual(self.parser.get_emails("example.com"), [])

    def test_get_comments(self):
        self.assertEqual(set(self.parser.get_comments()), {" hidden note "})

    def test_get_meta_redir(self):
        self.assertEqual(self.parser.get_meta_redir(), ["0;url=http://w3af.com/next"])

    def test_get_meta_tags(self):
        meta_tags = self.parser.get_meta_tags()

        self.assertIn({"name": "author", "content": "w3af"}, meta_tags)

    def test_clear_and_get_parser(self):
        self.assertIsInstance(self.parser.get_parser(), HTMLParser)
        self.parser.clear()

    def test_repr(self):
        self.assertEqual(
            repr(self.parser),
            f'<HTMLParser DocumentParser for "{self.response!r}">',
        )
        self.assertEqual(str(self.parser), repr(self.parser))

    def test_can_parse(self):
        self.assertTrue(DocumentParser.can_parse(self.response))
        self.assertFalse(
            DocumentParser.can_parse(_build_http_response("", "image/png"))
        )
        self.assertFalse(
            DocumentParser.can_parse(_build_http_response("x", "application/zip"))
        )

    def test_custom_parsers(self):
        self.assertRaises(BaseFrameworkException, DocumentParser, self.response, ())

    def test_url_sort_key(self):
        self.assertEqual(url_sort_key(URL("http://w3af.com/x")), "http://w3af.com/x")
