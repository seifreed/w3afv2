"""
test_cookie_handler.py

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

import http.cookiejar
import tempfile
import unittest
import urllib.request
from pathlib import Path

from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.url.extended_urllib import ExtendedUrllib
from w3af.core.data.url.handlers.cookie_handler import CookieHandler
from w3af.core.data.url.http_request import HTTPRequest
from w3af.core.data.url.tests.helpers.route_server import Response, RouteServer

COOKIE_VALUE = "session=123456789"

# IMPORTANT NOTE: Please remember that the cookie expiration, 2736616305, is
# going to limit the date until which this unittest will PASS
COOKIEJAR = (
    "# Netscape HTTP Cookie File\n"
    "127.0.0.1\tFALSE\t/\tFALSE\t2736616305\tsession\t123456789\n"
)


def check_cookie(request):
    received_cookie_value = request.headers.get("cookie")

    if received_cookie_value is None:
        return Response(body="Cookie not sent")
    if received_cookie_value == COOKIE_VALUE:
        return Response(body="Cookie received")
    return Response(body=f"Cookie {received_cookie_value} received")


class TestCookieHandler(unittest.TestCase):
    def setUp(self):
        self.server = RouteServer(
            {
                "/send-cookie": Response(headers=[("Set-Cookie", COOKIE_VALUE)]),
                "/send-cookie1": Response(headers=[("Set-Cookie", "11111111")]),
                "/send-cookie2": Response(headers=[("Set-Cookie", "222222222")]),
                "/check-cookie": check_cookie,
            }
        ).start()
        self.addCleanup(self.server.stop)
        self.send_cookie = URL(self.server.url("/send-cookie"))
        self.check_cookie = URL(self.server.url("/check-cookie"))

    def opener_get(self, opener, url, cookies=True):
        return opener.open(HTTPRequest(url, cookies=cookies)).read()

    def test_low_level(self):
        opener = urllib.request.build_opener(CookieHandler)

        # With this request the CookieHandler should store a cookie in its
        # cookiejar
        self.opener_get(opener, self.send_cookie)

        # And now it will send it because we're setting cookie to True
        self.assertIn(b"Cookie received", self.opener_get(opener, self.check_cookie))

        # And now it will NOT send any cookie because we're setting cookie to False
        self.assertIn(
            b"Cookie not sent",
            self.opener_get(opener, self.check_cookie, cookies=False),
        )

        # And now it will send it because we're setting cookie to True
        self.assertIn(b"Cookie received", self.opener_get(opener, self.check_cookie))

    def test_low_level_with_cookie_jar(self):
        with tempfile.TemporaryDirectory() as directory:
            cookie_file = Path(directory, "cookies.txt")
            cookie_file.write_text(COOKIEJAR)

            cj = http.cookiejar.MozillaCookieJar()
            cj.load(str(cookie_file), ignore_discard=True, ignore_expires=True)

        opener = urllib.request.build_opener(CookieHandler(cj))

        # Verify cookie from cookie jar is sent
        self.assertIn(b"Cookie received", self.opener_get(opener, self.check_cookie))

        # And now it will NOT send any cookie because we're setting cookie to False
        self.assertIn(
            b"Cookie not sent",
            self.opener_get(opener, self.check_cookie, cookies=False),
        )

    def test_requests_without_session_support_are_not_modified(self):
        request = urllib.request.Request(self.check_cookie.url_string)
        request.cookies = True

        self.assertIs(CookieHandler().http_request(request), request)
        self.assertFalse(request.has_header("Cookie"))

    def test_clear_cookies(self):
        handler = CookieHandler()
        opener = urllib.request.build_opener(handler)
        opener.open(HTTPRequest(self.send_cookie)).read()
        session_request = HTTPRequest(self.send_cookie, session=1)
        opener.open(session_request).read()

        handler.clear_cookies()

        self.assertEqual(len(handler.default_cookiejar), 0)
        self.assertEqual(len(handler.jars[1]), 0)

    def test_xurllib(self):
        uri_opener = ExtendedUrllib()
        self.addCleanup(uri_opener.end)
        uri_opener.GET(self.send_cookie)

        resp = uri_opener.GET(self.check_cookie, cookies=True)
        self.assertIn("Cookie received", resp)

        resp = uri_opener.GET(self.check_cookie, cookies=False)
        self.assertIn("Cookie not sent", resp)

        resp = uri_opener.GET(self.check_cookie, cookies=True)
        self.assertIn("Cookie received", resp)

    def test_sessions_basic(self):
        uri_opener = ExtendedUrllib()
        self.addCleanup(uri_opener.end)
        session_1 = uri_opener.get_new_session()
        session_2 = uri_opener.get_new_session()

        uri_opener.GET(self.send_cookie, session=session_1)

        resp = uri_opener.GET(self.check_cookie, cookies=True, session=session_1)
        self.assertIn("Cookie received", resp)

        resp = uri_opener.GET(self.check_cookie, cookies=True, session=session_2)
        self.assertIn("Cookie not sent", resp)

    def test_sessions_simultaneous(self):
        uri_opener = ExtendedUrllib()
        self.addCleanup(uri_opener.end)
        session_1 = uri_opener.get_new_session()
        session_2 = uri_opener.get_new_session()

        uri_opener.GET(URL(self.server.url("/send-cookie1")), session=session_1)
        uri_opener.GET(URL(self.server.url("/send-cookie2")), session=session_2)

        resp = uri_opener.GET(self.check_cookie, session=session_1)
        self.assertIn("Cookie 11111111 received", resp.body)

        resp = uri_opener.GET(self.check_cookie, session=session_2)
        self.assertIn("Cookie 222222222 received", resp)
