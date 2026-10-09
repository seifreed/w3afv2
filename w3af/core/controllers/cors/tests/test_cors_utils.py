"""
test_utils.py

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

import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from w3af.core.controllers.cors.utils import (
    build_cors_request,
    provides_cors_features,
    retrieve_cors_header,
)
from w3af.core.data.dc.headers import Headers
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.request.fuzzable_request import FuzzableRequest
from w3af.core.data.url.extended_urllib import ExtendedUrllib
from w3af.core.data.url.http_response import HTTPResponse


def cors_server(allow_origin):
    """
    Start a local HTTP server which records the Origin header of every
    request and, when allow_origin is set, answers with that value in the
    Access-Control-Allow-Origin header.
    """
    received_origins = []

    class CORSHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            received_origins.append(self.headers.get("Origin"))
            self.send_response(200)
            if allow_origin is not None:
                self.send_header("Access-Control-Allow-Origin", allow_origin)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def log_message(self, *args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), CORSHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, received_origins


class TestUtils(unittest.TestCase):

    def setUp(self):
        self.uri_opener = ExtendedUrllib()

    def tearDown(self):
        self.uri_opener.end()

    def start_server(self, allow_origin):
        server, received_origins = cors_server(allow_origin)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        url = URL(f"http://127.0.0.1:{server.server_port}/")
        return FuzzableRequest(url), received_origins

    def test_provides_cors_features_fails(self):
        self.assertRaises(AttributeError, provides_cors_features, None, None, None)

    def test_provides_cors_features_false(self):
        fr, received_origins = self.start_server(allow_origin=None)

        cors = provides_cors_features(fr, self.uri_opener, None)

        self.assertFalse(cors)
        self.assertEqual(received_origins, [None, "www.w3af.org"])

    def test_provides_cors_features_true(self):
        fr, received_origins = self.start_server(allow_origin="http://www.w3af.org/")

        cors = provides_cors_features(fr, self.uri_opener, None)

        self.assertTrue(cors)
        self.assertEqual(received_origins, [None])

    def test_retrieve_cors_header_true(self):
        url = URL("http://moth/")

        w3af_url = "http://www.w3af.org/"
        hrds = list({"Access-Control-Allow-Origin": w3af_url}.items())
        cors_headers = Headers(hrds)
        http_response = HTTPResponse(200, "", cors_headers, url, url)

        value = retrieve_cors_header(http_response, "Access-Control-Allow-Origin")

        self.assertEqual(value, w3af_url)

    def test_retrieve_cors_header_false(self):
        url = URL("http://moth/")

        cors_headers = Headers(list({"Access-Control": "Allow-Origin"}.items()))
        http_response = HTTPResponse(200, "", cors_headers, url, url)

        value = retrieve_cors_header(http_response, "Access-Control-Allow-Origin")

        self.assertEqual(value, None)

    def test_build_cors_request_true(self):
        url = URL("http://moth/")

        fr = build_cors_request(url, "http://foo.com/")

        self.assertEqual(fr.get_url(), url)
        self.assertEqual(fr.get_method(), "GET")
        self.assertEqual(
            fr.get_headers(), Headers(list({"Origin": "http://foo.com/"}.items()))
        )

    def test_build_cors_request_false(self):
        url = URL("http://moth/")

        fr = build_cors_request(url, None)

        self.assertEqual(fr.get_url(), url)
        self.assertEqual(fr.get_method(), "GET")
        self.assertEqual(fr.get_headers(), Headers())
