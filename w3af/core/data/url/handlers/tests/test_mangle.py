"""
test_mangle.py

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

from w3af.core.controllers.plugins.mangle_plugin import ManglePlugin
from w3af.core.controllers.w3af_core import w3afCore
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.url import opener_settings
from w3af.core.data.url.handlers.mangle import MangledKeepAliveHTTPResponse
from w3af.core.data.url.handlers.tests.local_server import LocalServer, Reply
from w3af.core.data.url.http_request import HTTPRequest


class SwapWords(ManglePlugin):
    """
    A mangle plugin which tags the requests and rewrites the response body.
    """

    def mangle_request(self, request):
        request.add_unredirected_header("X-Mangled", "yes")
        return request

    def mangle_response(self, response):
        response.set_body(response.get_body().replace("original", "mangled"))
        return self._fix_content_len(response)


class TestMangleHandler(unittest.TestCase):
    def setUp(self):
        self.server = LocalServer({"/": Reply(body="original body")}).start()
        self.addCleanup(self.server.stop)

    def open(self, plugins):
        settings = opener_settings.OpenerSettings()
        settings.set_mangle_plugins(plugins)
        settings.build_openers()
        request = HTTPRequest(URL(self.server.url()))
        return settings.get_custom_opener().open(request)

    def test_plugins_mangle_requests_and_responses(self):
        response = self.open([SwapWords()])

        self.assertIsInstance(response, MangledKeepAliveHTTPResponse)
        self.assertEqual(response.read(), "mangled body")
        self.assertEqual(response.code, 200)
        self.assertEqual(response.msg, "OK")
        self.assertEqual(response.geturl(), self.server.url())
        self.assertEqual(response.info()["Content-Length"], "12")
        self.assertEqual(response.encoding, "utf-8")
        self.assertEqual(self.server.requests[0].headers["X-Mangled"], "yes")
        response.close()

    def test_without_plugins_nothing_changes(self):
        response = self.open([])

        self.assertNotIsInstance(response, MangledKeepAliveHTTPResponse)
        self.assertEqual(response.read(), b"original body")

    def test_mangle_handler_raw_request_1326(self):
        """
        Reproduces [0] to make sure we don't make that mistake again.

        [0] https://github.com/andresriancho/w3af/issues/1326
        """
        http_request = f"GET {self.server.url()} HTTP/1.1\nHost: localhost\nFoo: bar\n"

        w3af_core = w3afCore()
        self.addCleanup(w3af_core.worker_pool.terminate_join)
        w3af_core.plugins.set_plugins(["sed"], "mangle")
        w3af_core.plugins.init_plugins()

        resp = w3af_core.uri_opener.send_raw_request(http_request, None)
        self.assertEqual(resp.get_code(), 200)
