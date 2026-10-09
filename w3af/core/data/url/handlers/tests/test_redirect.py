"""
test_redirect.py

Copyright 2013 Andres Riancho

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
import urllib.error
import urllib.request

from w3af.core.data.constants.response_codes import FOUND, MOVED_PERMANENTLY, OK
from w3af.core.data.misc.number_generator import consecutive_number_generator
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.url import opener_settings
from w3af.core.data.url.extended_urllib import ExtendedUrllib
from w3af.core.data.url.handlers.redirect import HTTP30XHandler
from w3af.core.data.url.http_request import HTTPRequest
from w3af.core.data.url.tests.helpers.route_server import Response, RouteServer

SRC_PATH = "/src"
DEST_PATH = "/dest"
OK_BODY = "Body!"


class RedirectServerTestCase(unittest.TestCase):

    def setUp(self):
        consecutive_number_generator.reset()
        self.server = RouteServer()
        self.server.start()
        self.redir_src = self.server.url(SRC_PATH)
        self.redir_dest = self.server.url(DEST_PATH)

    def tearDown(self):
        self.server.stop()

    def add_redirect(self, path, status, headers):
        self.server.add("GET", path, Response(status=status, headers=headers))


class TestRedirectHandlerLowLevel(RedirectServerTestCase):

    def setUp(self):
        super().setUp()
        self.add_redirect(SRC_PATH, FOUND, [("Location", self.redir_dest)])
        self.server.add("GET", DEST_PATH, Response(status=FOUND, body=OK_BODY))

    def test_redirect_handler(self):
        """
        Test the redirect handler using urllib2
        """
        opener = urllib.request.build_opener(HTTP30XHandler)

        request = urllib.request.Request(URL(self.redir_src).url_string)

        # This is because the 30x handler doesn't implement default error handling
        # which is in another part of the w3af framework and this is just a urllib2
        # level test
        self.assertRaises(urllib.error.HTTPError, opener.open, request)

    def test_handler_order(self):
        """
        Get an instance of the extended urllib and verify that the redirect
        handler still works, even when mixed with all the other handlers.
        """
        settings = opener_settings.OpenerSettings()
        settings.build_openers()
        opener = settings.get_custom_opener()

        request = HTTPRequest(URL(self.redir_src))
        response = opener.open(request)

        self.assertEqual(response.code, FOUND)
        self.assertEqual(response.id, 1)


class TestRedirectHandlerExtendedUrllib(RedirectServerTestCase):
    """
    Test the redirect handler using ExtendedUrllib
    """

    def setUp(self):
        super().setUp()
        self.uri_opener = ExtendedUrllib()

    def tearDown(self):
        self.uri_opener.end()
        super().tearDown()

    def test_redirect_302_simple_no_follow(self):
        self.add_redirect(SRC_PATH, FOUND, [("Location", self.redir_dest)])

        response = self.uri_opener.GET(URL(self.redir_src))

        location, _ = response.get_headers().iget("location")
        self.assertEqual(location, self.redir_dest)
        self.assertEqual(response.get_code(), FOUND)
        self.assertEqual(response.get_id(), 1)

    def test_redirect_302_simple_follow(self):
        self.add_redirect(SRC_PATH, FOUND, [("Location", self.redir_dest)])
        self.server.add("GET", DEST_PATH, Response(body=OK_BODY))

        response = self.uri_opener.GET(URL(self.redir_src), follow_redirects=True)

        self.assertEqual(response.get_code(), OK)
        self.assertEqual(response.get_body(), OK_BODY)
        self.assertEqual(response.get_redir_uri(), URL(self.redir_dest))
        self.assertEqual(response.get_url(), URL(self.redir_src))
        self.assertEqual(response.get_id(), 2)

    def test_redirect_301_loop(self):
        self.add_redirect(SRC_PATH, MOVED_PERMANENTLY, [("Location", self.redir_dest)])
        self.add_redirect(DEST_PATH, MOVED_PERMANENTLY, [("URI", self.redir_src)])

        response = self.uri_opener.GET(URL(self.redir_src), follow_redirects=True)

        # At some point the handler detects a loop and stops
        self.assertEqual(response.get_code(), MOVED_PERMANENTLY)
        self.assertEqual(response.get_body(), "")
        self.assertEqual(response.get_id(), 9)

    def test_redirect_302_without_location_returns_302_response(self):
        # Breaks the RFC
        self.add_redirect(SRC_PATH, FOUND, [])

        response = self.uri_opener.GET(URL(self.redir_src), follow_redirects=True)

        # Doesn't follow the redirects
        self.assertEqual(response.get_code(), FOUND)
        self.assertEqual(response.get_body(), "")
        self.assertEqual(response.get_id(), 1)

    def test_redirect_no_follow_file_proto(self):
        self.add_redirect(SRC_PATH, FOUND, [("Location", "file:///etc/passwd")])

        response = self.uri_opener.GET(URL(self.redir_src), follow_redirects=True)

        self.assertEqual(response.get_code(), FOUND)
        self.assertEqual(response.get_body(), "")
        self.assertEqual(response.get_url(), URL(self.redir_src))
        self.assertEqual(response.get_id(), 1)
