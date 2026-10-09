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

OK_BODY = "Body!"


def redirect(code, location, header="Location"):
    return Response(code, headers=[(header, location)])


class RedirectServerTestCase(unittest.TestCase):
    def setUp(self):
        consecutive_number_generator.reset()
        self.server = RouteServer().start()
        self.addCleanup(self.server.stop)
        self.src = self.server.url("/src")
        self.dest = self.server.url("/dest")

    def route(self, path, reply):
        self.server.routes[path] = reply


class TestRedirectHandlerLowLevel(RedirectServerTestCase):
    def test_redirect_handler(self):
        """
        Test the redirect handler using urllib2
        """
        self.route("/src", redirect(FOUND, self.dest))
        self.route("/dest", Response(FOUND, OK_BODY))

        opener = urllib.request.build_opener(HTTP30XHandler)
        request = urllib.request.Request(self.src)

        # This is because the 30x handler doesn't implement default error handling
        # which is in another part of the w3af framework and this is just a urllib2
        # level test
        self.assertRaises(urllib.error.HTTPError, opener.open, request)

    def test_handler_order(self):
        """
        Get an instance of the extended urllib and verify that the redirect
        handler still works, even when mixed with all the other handlers.
        """
        self.route("/src", redirect(FOUND, self.dest))
        self.route("/dest", Response(FOUND, OK_BODY))

        settings = opener_settings.OpenerSettings()
        settings.build_openers()
        opener = settings.get_custom_opener()

        response = opener.open(HTTPRequest(URL(self.src)))

        self.assertEqual(response.code, FOUND)
        self.assertEqual(response.id, 1)

    def post(self):
        settings = opener_settings.OpenerSettings()
        settings.build_openers()
        request = HTTPRequest(URL(self.src), data="a=1", follow_redirects=True)
        return settings.get_custom_opener().open(request)

    def test_redirect_after_post_uses_get(self):
        self.route("/src", redirect(FOUND, "/dest"))
        self.route("/dest", Response(OK, OK_BODY))

        response = self.post()

        self.assertEqual(response.read(), OK_BODY.encode())
        self.assertEqual(
            [(r.method, r.path) for r in self.server.requests],
            [("POST", "/src"), ("GET", "/dest")],
        )

    def test_307_after_post_is_not_followed(self):
        self.route("/src", redirect(307, self.dest))

        response = self.post()

        self.assertEqual(response.code, 307)
        self.assertEqual(len(self.server.requests), 1)


class TestRedirectHandlerExtendedUrllib(RedirectServerTestCase):
    """
    Test the redirect handler using ExtendedUrllib
    """

    def setUp(self):
        super().setUp()
        self.uri_opener = ExtendedUrllib()

    def tearDown(self):
        self.uri_opener.end()

    def test_redirect_302_simple_no_follow(self):
        self.route("/src", redirect(FOUND, self.dest))

        response = self.uri_opener.GET(URL(self.src))

        location, _ = response.get_headers().iget("location")
        self.assertEqual(location, self.dest)
        self.assertEqual(response.get_code(), FOUND)
        self.assertEqual(response.get_id(), 1)

    def test_redirect_302_simple_follow(self):
        self.route("/src", redirect(FOUND, self.dest))
        self.route("/dest", Response(OK, OK_BODY))

        response = self.uri_opener.GET(URL(self.src), follow_redirects=True)

        self.assertEqual(response.get_code(), OK)
        self.assertEqual(response.get_body(), OK_BODY)
        self.assertEqual(response.get_redir_uri(), URL(self.dest))
        self.assertEqual(response.get_url(), URL(self.src))
        self.assertEqual(response.get_id(), 2)

    def test_redirect_301_loop(self):
        self.route("/src", redirect(MOVED_PERMANENTLY, self.dest))
        self.route("/dest", redirect(MOVED_PERMANENTLY, self.src, header="URI"))

        response = self.uri_opener.GET(URL(self.src), follow_redirects=True)

        # At some point the handler detects a loop and stops
        self.assertEqual(response.get_code(), MOVED_PERMANENTLY)
        self.assertEqual(response.get_body(), "")
        self.assertEqual(response.get_id(), 9)

    def test_too_many_redirections(self):
        hops = HTTP30XHandler.max_redirections + 2
        for hop in range(hops):
            self.route(f"/hop{hop}", redirect(FOUND, f"/hop{hop + 1}"))

        response = self.uri_opener.GET(
            URL(self.server.url("/hop0")), follow_redirects=True
        )

        self.assertEqual(response.get_code(), FOUND)
        self.assertEqual(len(self.server.requests), HTTP30XHandler.max_redirections + 1)

    def test_redirect_302_without_location_returns_302_response(self):
        # Breaks the RFC
        self.route("/src", Response(FOUND))

        response = self.uri_opener.GET(URL(self.src), follow_redirects=True)

        # Doesn't follow the redirects
        self.assertEqual(response.get_code(), FOUND)
        self.assertEqual(response.get_body(), "")
        self.assertEqual(response.get_id(), 1)

    def test_redirect_to_an_invalid_url_is_not_followed(self):
        self.route("/src", redirect(FOUND, "http://[invalid"))

        response = self.uri_opener.GET(URL(self.src), follow_redirects=True)

        self.assertEqual(response.get_code(), FOUND)
        self.assertEqual(len(self.server.requests), 1)

    def test_redirect_no_follow_file_proto(self):
        self.route("/src", redirect(FOUND, "file:///etc/passwd"))

        response = self.uri_opener.GET(URL(self.src), follow_redirects=True)

        self.assertEqual(response.get_code(), FOUND)
        self.assertEqual(response.get_body(), "")
        self.assertEqual(response.get_url(), URL(self.src))
        self.assertEqual(response.get_id(), 1)
