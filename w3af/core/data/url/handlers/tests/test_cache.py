"""
test_cache.py

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

import io
import unittest
import urllib.response
from email.message import Message

from w3af.core.data.db.exceptions import DBException
from w3af.core.data.db.history import HistoryItem
from w3af.core.data.dc.headers import Headers
from w3af.core.data.misc.number_generator import NumberGenerator
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.url import opener_settings
from w3af.core.data.url.director import CustomOpenerDirector, build_opener
from w3af.core.data.url.exceptions import CacheStoreException
from w3af.core.data.url.handlers.cache import CacheHandler
from w3af.core.data.url.handlers.cache_backend.cached_response import CachedResponse
from w3af.core.data.url.handlers.cache_backend.db import SQLCachedResponse, store_error
from w3af.core.data.url.handlers.cache_backend.utils import gen_hash
from w3af.core.data.url.handlers.keepalive import HTTPHandler
from w3af.core.data.url.http_request import HTTPRequest
from w3af.core.data.url.http_response import HTTPResponse
from w3af.core.data.url.tests.helpers.route_server import Response, RouteServer
from w3af.core.exceptions import ScanMustStopException


class TestCacheHandler(unittest.TestCase):
    def setUp(self):
        self.id_generator = NumberGenerator()
        self.cache = CacheHandler(self.id_generator)
        self.addCleanup(self.cache.clear)
        self.server = RouteServer(
            {"/": Response(body="spameggs", headers=[("X-Test", "cached")])}
        ).start()
        self.addCleanup(self.server.stop)
        self.url = URL(self.server.url())
        self.opener = build_opener(CustomOpenerDirector, [HTTPHandler(), self.cache])

    def test_responses_are_served_from_the_cache(self):
        live = self.opener.open(HTTPRequest(self.url, cache=True))
        cached = self.opener.open(HTTPRequest(self.url, cache=True))

        self.assertEqual(len(self.server.requests), 1)
        self.assertIsInstance(cached, SQLCachedResponse)
        self.assertTrue(cached.from_cache)
        self.assertEqual(cached.code, live.code)
        self.assertEqual(cached.msg, live.msg)
        self.assertEqual(cached.read(), "spameggs")
        self.assertEqual(cached.info()["X-Test"], "cached")
        self.assertIs(cached.headers(), cached.info())
        self.assertEqual(cached.geturl(), self.url.url_string)
        self.assertEqual(cached.get_full_url(), self.url.url_string)
        self.assertEqual(cached.encoding, "utf-8")
        self.assertGreaterEqual(cached.get_wait_time(), 0)

    def test_requests_which_should_not_use_the_cache(self):
        self.opener.open(HTTPRequest(self.url, cache=True))

        self.opener.open(HTTPRequest(self.url, cache=False))
        self.opener.open(HTTPRequest(self.url, cache=True, data="a=1"))

        self.assertEqual(
            [request.method for request in self.server.requests],
            ["GET", "GET", "POST"],
        )

    def test_cached_response_keeps_headers(self):
        url = URL("http://www.w3af.org/")
        request = HTTPRequest(url, cache=True)

        headers = Headers([("Content-Type", "text/html")])
        response = HTTPResponse(200, "<html/>", headers, url, url, msg="OK")
        response.set_id(self.id_generator.inc())
        response.set_alias(gen_hash(request))

        history = HistoryItem()
        history.request = request
        history.response = response
        history.save()

        cached_response = SQLCachedResponse(request)
        self.assertEqual(cached_response.info()["Content-Type"], "text/html")
        self.assertRaises(ValueError, cached_response._get_from_response, "PART_FOO")

    def test_store_errors(self):
        request = HTTPRequest(self.url, cache=True)
        response = urllib.response.addinfourl(
            io.BytesIO(b"body"), Message(), self.url.url_string, code="abc"
        )
        response.msg = "OK"
        response.id = 1

        with self.assertRaises(CacheStoreException):
            self.cache.http_response(request, response)

    def test_running_out_of_disk_stops_the_scan(self):
        request = HTTPRequest(self.url)
        response = HTTPResponse(200, "", Headers(), self.url, self.url)

        error = store_error(DBException("database or disk is full"), request, response)
        self.assertIsInstance(error, ScanMustStopException)

        error = store_error(ValueError("invalid"), request, response)
        self.assertIsInstance(error, CacheStoreException)


class TestCachedResponseInterface(unittest.TestCase):
    def test_backends_must_implement_the_storage(self):
        self.assertRaises(
            NotImplementedError, CachedResponse.store_in_cache, None, None
        )
        self.assertRaises(NotImplementedError, CachedResponse.init)
        self.assertRaises(
            NotImplementedError,
            CachedResponse,
            HTTPRequest(URL("http://w3af.org/")),
        )


class CacheIntegrationTest(unittest.TestCase):
    def test_cache_http_errors(self):
        settings = opener_settings.OpenerSettings()
        settings.build_openers()
        opener = settings.get_custom_opener()

        with RouteServer() as server:
            url = URL(server.url("/foo-bar-not-exists.htm"))
            response = opener.open(HTTPRequest(url, cache=False))

            # If there is a response we should store it, even if it is a 404
            self.assertEqual(response.status, 404)
            cached = opener.open(HTTPRequest(url, cache=True))

        self.assertIsInstance(cached, SQLCachedResponse)
        self.assertEqual(cached.code, 404)
        self.assertEqual(len(server.requests), 1)
