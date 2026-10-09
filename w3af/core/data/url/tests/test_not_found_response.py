"""
test_not_found_response.py

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
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.url.http_response import HTTPResponse
from w3af.core.data.url.not_found_response import FourOhFourResponse
from w3af.core.data.url.response_cleaner import get_clean_body_from_parts


def http_response(url, body, content_type="text/html"):
    url = URL(url)
    headers = Headers([("Content-Type", content_type)])
    return HTTPResponse(404, body, headers, url, url, _id=7)


class TestFourOhFourResponse(unittest.TestCase):

    def test_from_http_response(self):
        response = http_response(
            "http://w3af.org/abc/missing-page.html",
            "<p>missing-page.html was not found</p>",
        )

        not_found = FourOhFourResponse.from_http_response(response)

        self.assertEqual(not_found.normalized_path, "http://w3af.org/abc/filename.html")
        self.assertEqual(not_found.content_type, "text/html")
        self.assertEqual(not_found.url, "http://w3af.org/abc/missing-page.html")
        self.assertEqual(not_found.id, 7)
        self.assertEqual(not_found.code, 404)

        # The body is cleaned (the requested path is removed) only once
        self.assertEqual(not_found.body, "<p> was not found</p>")
        self.assertEqual(not_found.body, "<p> was not found</p>")

    def test_serialization_roundtrip(self):
        response = http_response("http://w3af.org/abc/def", "Nothing here")
        not_found = FourOhFourResponse.from_http_response(response)

        loaded = FourOhFourResponse.loads(not_found.dumps())

        self.assertEqual(loaded.body, "Nothing here")
        self.assertEqual(loaded.normalized_path, not_found.normalized_path)
        self.assertEqual(loaded.to_dict(), not_found.to_dict())
        self.assertEqual(loaded, FourOhFourResponse.from_dict(not_found.to_dict()))

    def test_equality(self):
        response = http_response("http://w3af.org/abc/def", "Nothing here")

        first = FourOhFourResponse.from_http_response(response)
        self.assertEqual(first.body, "Nothing here")
        same = FourOhFourResponse.from_dict(first.to_dict())
        other = FourOhFourResponse.from_dict(dict(first.to_dict(), code=403))

        self.assertEqual(first, same)
        self.assertNotEqual(first, other)

    def test_normalize_path(self):
        expected = {
            "http://w3af.org/": "http://w3af.org/",
            "http://w3af.org/?id=1": "http://w3af.org/",
            "http://w3af.org/abc/def.html": "http://w3af.org/abc/filename.html",
            "http://w3af.org/abc/def": "http://w3af.org/abc/filename",
            "http://w3af.org/abc/": "http://w3af.org/path/",
            "http://w3af.org/abc/def/": "http://w3af.org/abc/path/",
            "http://w3af.org/abc?id=1": "http://w3af.org/filename",
        }

        for url, normalized in expected.items():
            self.assertEqual(
                FourOhFourResponse.normalize_path(URL(url)), normalized, url
            )

    def test_repr(self):
        not_found = FourOhFourResponse(url="http://w3af.org/x", code=404)
        self.assertEqual(
            repr(not_found), "<FourOhFourResponse (url:http://w3af.org/x, code:404)>"
        )


class TestResponseCleaner(unittest.TestCase):

    def test_non_text_bodies_are_not_cleaned(self):
        uri = URL("http://w3af.org/image-name.png")

        body = get_clean_body_from_parts(
            b"image-name.png", uri, HTTPResponse.DOC_TYPE_IMAGE
        )

        self.assertEqual(body, b"image-name.png")
