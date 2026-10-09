"""
test_basic_handlers.py

Copyright 2026 w3af contributors

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

import gzip
import unittest
import urllib.request
import zlib

from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.url.director import CustomOpenerDirector, build_opener
from w3af.core.data.url.handlers.cache import CacheHandler
from w3af.core.data.url.handlers.fast_basic_auth import FastHTTPBasicAuthHandler
from w3af.core.data.url.handlers.gzip_handler import HTTPGzipProcessor
from w3af.core.data.url.handlers.keepalive import HTTPHandler
from w3af.core.data.url.handlers.normalize import NormalizeHandler
from w3af.core.data.url.http_request import HTTPRequest
from w3af.core.data.url.tests.helpers.route_server import Response, RouteServer

BODY = b"decompressed body"


def compressed(body, encoding):
    return Response(body=body, headers=[("Content-Encoding", encoding)])


def raw_deflate(body):
    compressor = zlib.compressobj(wbits=-zlib.MAX_WBITS)
    return compressor.compress(body) + compressor.flush()


class TestGzipProcessor(unittest.TestCase):
    def setUp(self):
        self.server = RouteServer(
            {
                "/gzip": compressed(gzip.compress(BODY), "gzip"),
                "/zlib": compressed(zlib.compress(BODY), "deflate"),
                "/raw": compressed(raw_deflate(BODY), "deflate"),
                "/compress": compressed(gzip.compress(BODY), "compress"),
                "/broken": compressed(b"not compressed", "gzip"),
                "/plain": Response(body=BODY),
            }
        ).start()
        self.addCleanup(self.server.stop)
        self.gzip_processor = HTTPGzipProcessor()
        self.cache = CacheHandler()
        self.addCleanup(self.cache.clear)
        self.opener = build_opener(
            CustomOpenerDirector, [HTTPHandler(), self.gzip_processor, self.cache]
        )

    def get(self, path, cache=False):
        return self.opener.open(HTTPRequest(URL(self.server.url(path)), cache=cache))

    def test_decompression_methods(self):
        for path in ("/gzip", "/zlib", "/raw", "/compress", "/zlib", "/gzip"):
            self.assertEqual(self.get(path).read(), BODY, path)

        self.assertEqual(
            self.server.requests[0].headers["Accept-encoding"], "gzip, deflate"
        )

    def test_the_last_working_method_is_tried_first(self):
        self.get("/raw")

        self.assertEqual(
            self.gzip_processor._decompression_methods[0],
            self.gzip_processor._zlib_1,
        )

    def test_bodies_which_cannot_be_decompressed_are_kept(self):
        self.assertEqual(self.get("/broken").read(), b"not compressed")

    def test_uncompressed_and_cached_responses_are_untouched(self):
        self.assertEqual(self.get("/plain", cache=True).read(), BODY)
        self.assertEqual(self.get("/plain", cache=True).read(), BODY.decode())
        self.assertEqual(len(self.server.requests), 1)


class TestFastBasicAuth(unittest.TestCase):
    def setUp(self):
        self.server = RouteServer({"/": Response(body="ok")}).start()
        self.addCleanup(self.server.stop)
        password_manager = urllib.request.HTTPPasswordMgrWithDefaultRealm()
        password_manager.add_password(None, self.server.url(), "user", "pass")
        self.opener = build_opener(
            CustomOpenerDirector,
            [HTTPHandler(), FastHTTPBasicAuthHandler(password_manager)],
        )

    def authorization_sent(self, url, use_basic_auth=True):
        self.opener.open(HTTPRequest(URL(url), use_basic_auth=use_basic_auth))
        return self.server.requests[-1].headers.get("Authorization")

    def test_credentials_are_sent_without_waiting_for_a_401(self):
        self.assertEqual(
            self.authorization_sent(self.server.url()), "Basic dXNlcjpwYXNz"
        )

    def test_requests_can_opt_out(self):
        self.assertIsNone(self.authorization_sent(self.server.url(), False))

    def test_urls_without_credentials(self):
        url = f"http://localhost:{self.server.port}/"
        self.assertIsNone(self.authorization_sent(url))


class TestNormalizeHandler(unittest.TestCase):
    def test_required_headers_are_added(self):
        request = HTTPRequest(URL("http://w3af.org/"))

        NormalizeHandler().http_request(request)

        self.assertEqual(request.unredirected_hdrs["Host"], "w3af.org")
        self.assertEqual(request.unredirected_hdrs["Accept-encoding"], "identity")

    def test_existing_headers_are_kept(self):
        request = HTTPRequest(
            URL("http://w3af.org/"),
            headers={"Host": "example.com", "Accept-Encoding": "gzip"},
        )

        NormalizeHandler().http_request(request)

        self.assertEqual(request.unredirected_hdrs, {})
