"""
test_htmlparser_performance.py

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
import unittest
from pathlib import Path

from w3af import ROOT_PATH
from w3af.core.data.dc.headers import Headers
from w3af.core.data.parsers.doc.html import HTMLParser
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.url.http_response import HTTPResponse

SOME_TEXT = "This is placeholder text"
BLOCKS = 1000


def huge_html_document():
    """
    Build a big HTML document which is not real-life data, but forces the
    parser to deal with a lot of nodes: long and deep trees, forms, links,
    images and scripts.
    """
    lines = ["<html>", f"<title>{SOME_TEXT}</title>", "<body>"]

    for i in range(BLOCKS):
        lines += ["<p>", SOME_TEXT, f'<a href="/{i}">{SOME_TEXT}</a>', "</p>"]
        lines += [
            "<div>",
            f'<a href="/{i}">{SOME_TEXT}</a>',
            f'<form action="/{i}" method="POST">',
            f'<input type="text" name="abc-{i}">',
            "</form>",
            "</div>",
        ]

    for i in range(BLOCKS):
        lines += [
            "<div>",
            f'<img src="/img-{i}" />',
            f'<a href="mailto:andres{i}@test.com">{SOME_TEXT}</a>',
            "</div>",
        ]

    for i in range(BLOCKS):
        lines += [f'<div id="id-{i}">', f'<a href="/deep-div-{i}">{SOME_TEXT}</a>']

    for _ in range(BLOCKS):
        lines += ["<p>", SOME_TEXT, "</p>", "</div>"]

    lines += ["<script><!-- code(); --></script>"] * 50
    lines += ["</body>", "</html>"]

    return "\n".join(lines)


def html_response(body):
    url = URL("http://www.w3af.org/")
    headers = Headers([("content-type", "text/html")])
    return HTTPResponse(200, body, headers, url, url, charset="utf-8")


class TestHTMLParserLargeDocuments(unittest.TestCase):

    HTML_FILE = os.path.join(
        ROOT_PATH, "core", "data", "context", "tests", "samples", "django-500.html"
    )

    def test_parsing_the_same_response_repeatedly_is_stable(self):
        response = html_response(Path(self.HTML_FILE).read_text())

        results = []
        for _ in range(5):
            parser = HTMLParser(response)
            parser.parse()
            results.append((len(parser.forms), frozenset(parser.references[0])))

        self.assertEqual(len(set(results)), 1)

    def test_parse_huge_document(self):
        parser = HTMLParser(html_response(huge_html_document()))

        parser.parse()

        self.assertEqual(len(parser.forms), BLOCKS)
        self.assertEqual(len(parser.get_emails()), BLOCKS)
        parsed_paths = {url.get_path() for url in parser.references[0]}
        self.assertIn(f"/{BLOCKS - 1}", parsed_paths)
        self.assertIn(f"/img-{BLOCKS - 1}", parsed_paths)
