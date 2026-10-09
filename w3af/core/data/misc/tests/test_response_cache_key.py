"""
test_response_cache_key.py

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

from w3af.core.data.dc.headers import Headers
from w3af.core.data.misc.response_cache_key import (
    ResponseCacheKeyCache,
    get_response_cache_key,
)
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.url.http_response import HTTPResponse

HTML_HEADERS = Headers([("Content-Type", "text/html")])
XML_BONES_BODY = "<html><body>" + "<p>w3af</p>" * 30 + "</body></html>"


def build_response(body, path="/index.html"):
    url = URL(f"http://w3af.org{path}")
    return HTTPResponse(200, body, HTML_HEADERS, url, url)


class TestResponseCacheKey(unittest.TestCase):
    def test_same_response_same_key(self):
        key_1 = get_response_cache_key(build_response("abc"), headers="A: b")
        key_2 = get_response_cache_key(build_response("abc"), headers="A: b")

        self.assertIsInstance(key_1, str)
        self.assertEqual(key_1, key_2)

    def test_headers_change_key(self):
        response = build_response("abc")

        self.assertNotEqual(
            get_response_cache_key(response, headers="A: b"),
            get_response_cache_key(response, headers="A: c"),
        )

    def test_bytes_headers(self):
        response = build_response("abc")

        self.assertEqual(
            get_response_cache_key(response, headers=b"A: b"),
            get_response_cache_key(response, headers="A: b"),
        )

    def test_xml_bones_body(self):
        key_1 = get_response_cache_key(build_response(XML_BONES_BODY, "/a"))
        key_2 = get_response_cache_key(build_response(XML_BONES_BODY, "/a"))

        self.assertEqual(key_1, key_2)

    def test_cache_returns_stored_key(self):
        cache = ResponseCacheKeyCache()
        response = build_response("abc")

        self.assertEqual(
            cache.get_response_cache_key(response, headers="A: b"),
            get_response_cache_key(response, headers="A: b"),
        )
        self.assertEqual(
            cache.get_response_cache_key(response, headers="A: b"),
            cache.get_response_cache_key(build_response("abc"), headers="A: b"),
        )
