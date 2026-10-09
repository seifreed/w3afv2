"""
test_director.py

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

from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.url.director import CustomOpenerDirector, build_opener
from w3af.core.data.url.handlers.keepalive import HTTPHandler
from w3af.core.data.url.http_request import HTTPRequest
from w3af.core.data.url.response_meta import SUCCESS, ResponseMeta
from w3af.core.data.url.tests.helpers.route_server import RouteServer, echo


class TestCustomOpenerDirector(unittest.TestCase):

    def setUp(self):
        self.server = RouteServer.serve_for(self, {"/echo": echo})

    def test_build_opener_skips_replaced_default_handlers(self):
        keepalive = HTTPHandler()
        self.addCleanup(keepalive.close_all)

        opener = build_opener(
            CustomOpenerDirector, [keepalive, urllib.request.HTTPErrorProcessor]
        )
        handler_types = [type(handler) for handler in opener.handlers]

        # The keepalive handler replaces urllib's HTTPHandler, classes are
        # instantiated
        self.assertIn(HTTPHandler, handler_types)
        self.assertNotIn(urllib.request.HTTPHandler, handler_types)
        self.assertEqual(handler_types.count(urllib.request.HTTPErrorProcessor), 1)
        self.assertIn(urllib.request.UnknownHandler, handler_types)

    def test_open_keeps_the_request_timeout(self):
        opener = build_opener(CustomOpenerDirector, [])
        request = HTTPRequest(URL(self.server.url("/echo")), timeout=7)

        response = opener.open(request, timeout=1)

        self.assertEqual(request.timeout, 7)
        self.assertEqual(response.read().decode().splitlines()[0], "GET /echo")

    def test_open_with_data(self):
        opener = build_opener(CustomOpenerDirector, [])
        request = HTTPRequest(URL(self.server.url("/echo")), method="POST")

        response = opener.open(request, data=b"a=1")

        self.assertIn("a=1", response.read().decode())
        self.assertEqual(self.server.requests[-1].body, b"a=1")


class TestResponseMeta(unittest.TestCase):

    def test_str_and_repr(self):
        meta = ResponseMeta(True, SUCCESS, rtt=0.5, host="w3af.org")
        expected = (
            "<ResponseMeta (successful: True, message: Success, rtt: 0.5,"
            " host: w3af.org)"
        )

        self.assertEqual(str(meta), expected)
        self.assertEqual(repr(meta), expected)
