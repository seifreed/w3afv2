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

import unittest
import urllib.request

from w3af.core.data.db.history import HistoryItem
from w3af.core.data.dc.headers import Headers
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.url import opener_settings
from w3af.core.data.url.handlers.cache import CacheHandler
from w3af.core.data.url.handlers.cache_backend.db import SQLCachedResponse
from w3af.core.data.url.handlers.cache_backend.utils import gen_hash
from w3af.core.data.url.handlers.keepalive import HTTPHandler
from w3af.core.data.url.http_request import HTTPRequest
from w3af.core.data.url.http_response import HTTPResponse
from w3af.core.data.url.tests.helpers.route_server import Response, RouteServer

BODY = "spameggs"
CONTENT_TYPE = "text/html"


class CacheServerTestCase(unittest.TestCase):

    def setUp(self):
        self.server = RouteServer()
        self.server.add(
            "GET", "/", Response(body=BODY, headers=[("Content-Type", CONTENT_TYPE)])
        )
        self.server.start()

    def tearDown(self):
        self.server.stop()
        CacheHandler().clear()


class TestCacheHandler(CacheServerTestCase):

    def test_basic(self):
        url = URL(self.server.url("/"))
        request = HTTPRequest(url, cache=True)

        cache = CacheHandler()
        self.assertEqual(cache.default_open(request), None)

        # The opener sends the request to the server and the cache handler
        # stores the response
        opener = urllib.request.build_opener(HTTPHandler(), cache)
        response = opener.open(request)
        self.assertEqual(len(self.server.requests), 1)

        # This retrieves the response from the cache
        cached_response = cache.default_open(request)

        self.assertIsNotNone(cached_response)

        self.assertEqual(cached_response.code, response.code)
        self.assertEqual(cached_response.msg, response.msg)
        self.assertEqual(cached_response.read(), BODY)
        self.assertEqual(cached_response.info().get("content-type"), CONTENT_TYPE)
        self.assertEqual(cached_response.geturl(), url.url_string)
        self.assertEqual(len(self.server.requests), 1)

    def test_cached_response_keeps_headers(self):
        url = URL("http://www.w3af.org/")
        request = HTTPRequest(url, cache=True)
        CacheHandler()

        headers = Headers([("Content-Type", "text/html")])
        response = HTTPResponse(200, "<html/>", headers, url, url, msg="OK")
        response.set_id(1)
        response.set_alias(gen_hash(request))

        history = HistoryItem()
        history.request = request
        history.response = response
        history.save()

        cached_response = SQLCachedResponse(request)
        self.assertEqual(cached_response.info()["Content-Type"], "text/html")

    def test_no_cache(self):
        url = URL(self.server.url("/"))
        request = HTTPRequest(url, cache=False)

        cache = CacheHandler()
        self.assertEqual(cache.default_open(request), None)

        opener = urllib.request.build_opener(HTTPHandler(), cache)
        opener.open(request)

        self.assertEqual(cache.default_open(request), None)


class CacheIntegrationTest(CacheServerTestCase):
    def test_cache_http_errors(self):
        settings = opener_settings.OpenerSettings()
        settings.build_openers()
        opener = settings.get_custom_opener()

        url = URL(self.server.url("/foo-bar-not-exists.htm"))
        request = HTTPRequest(url, cache=False)

        # If there is a response we should store it, even if it is a 404
        response = opener.open(request)

        # And make sure the response was a 404
        self.assertEqual(response.status, 404)

        # Make sure the 404 response was stored in the cache
        stored_response = SQLCachedResponse(request)
        self.assertEqual(stored_response.code, 404)
