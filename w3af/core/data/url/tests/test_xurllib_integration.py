"""
test_xurllib_integration.py

Copyright 2011 Andres Riancho

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

import base64
import gzip
import os
import tempfile
import unittest
import zlib

import spnego
from spnego.exceptions import SpnegoError

from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.url.extended_urllib import ExtendedUrllib
from w3af.core.data.url.tests.helpers.route_server import Response, RouteServer

PAGE = "<html><body>View HTTP response headers.</body></html>"
NTLM_PATH = "/w3af/core/ntlm_auth/ntlm_v1/"


def compressed(encoding, compress):
    def responder(request):
        return Response(
            200,
            compress(PAGE.encode()),
            headers=[("Content-Encoding", encoding)],
        )

    return responder


def set_cookie(request):
    return Response(200, "cookie set", headers=[("Set-Cookie", "session=abc123")])


def ntlm_protected(request):
    """
    Authenticate the client using NTLM, the handshake state lives in the
    TCP connection just like in IIS.
    """
    authorization = request.headers.get("Authorization", "")
    challenge_header = [("WWW-Authenticate", "NTLM")]

    if not authorization.startswith("NTLM "):
        return Response(401, "Must authenticate.", headers=challenge_header)

    token = base64.b64decode(authorization[5:])
    context = request.connection.get("ntlm")

    if context is None:
        context = spnego.server(protocol="ntlm")
        request.connection["ntlm"] = context
        challenge_token = context.step(token)
        if challenge_token is None:
            return Response(401, "Missing challenge token", headers=challenge_header)
        challenge = base64.b64encode(challenge_token).decode("ascii")
        return Response(
            401, "Challenge", headers=[("WWW-Authenticate", f"NTLM {challenge}")]
        )

    try:
        context.step(token)
    except SpnegoError:
        request.connection.pop("ntlm")
        return Response(401, "Must authenticate.", headers=challenge_header)

    return Response(200, f"You are {context.client_principal}")


class TestXUrllibIntegration(unittest.TestCase):

    def setUp(self):
        self.uri_opener = ExtendedUrllib()
        self.addCleanup(self.uri_opener.end)
        self.addCleanup(self.uri_opener.settings.set_default_values)

        self.server = RouteServer.serve_for(
            self,
            {
                "/gzip.html": compressed("gzip", gzip.compress),
                "/deflate.html": compressed("deflate", zlib.compress),
                "/set-cookie": set_cookie,
                NTLM_PATH: ntlm_protected,
            },
        )

    def use_ntlm_user_file(self, contents):
        with tempfile.NamedTemporaryFile("w", delete=False) as user_file:
            user_file.write(contents)

        self.addCleanup(os.unlink, user_file.name)

        previous = os.environ.get("NTLM_USER_FILE")
        os.environ["NTLM_USER_FILE"] = user_file.name

        if previous is None:
            self.addCleanup(os.environ.pop, "NTLM_USER_FILE")
        else:
            self.addCleanup(os.environ.__setitem__, "NTLM_USER_FILE", previous)

    def configure_ntlm(self, domain, user, password, url):
        settings = self.uri_opener.settings
        options = settings.get_options()

        options["ntlm_auth_domain"].set_value(domain)
        options["ntlm_auth_user"].set_value(user)
        options["ntlm_auth_passwd"].set_value(password)
        options["ntlm_auth_url"].set_value(url)

        settings.set_options(options)

    def test_ntlm_auth_not_configured(self):
        url = URL(self.server.url(NTLM_PATH))
        http_response = self.uri_opener.GET(url, cache=False)

        self.assertEqual(http_response.get_code(), 401)
        self.assertIn("Must authenticate.", http_response.body)

    def test_ntlm_auth_valid_creds(self):
        """
        Fails until the handlers support NTLM: NoOpErrorHandler never gives
        the 401 challenge to HTTPNtlmAuthHandler, and the keepalive connection
        manager opens a new connection (instead of reusing the one that got
        the challenge) for the NTLM authenticate message.
        """
        self.use_ntlm_user_file("MOTH:admin:admin\n")
        url = self.server.url(NTLM_PATH)
        self.configure_ntlm("MOTH", "admin", "admin", url)

        http_response = self.uri_opener.GET(URL(url), cache=False)

        self.assertEqual(http_response.get_code(), 200)
        self.assertIn("You are MOTH\\admin", http_response.body)

    def test_gzip(self):
        res = self.uri_opener.GET(URL(self.server.url("/gzip.html")), cache=False)

        content_encoding, _ = res.get_headers().iget("content-encoding", "")
        self.assertIn("gzip", content_encoding)
        self.assertIn("View HTTP response headers.", res.get_body())

    def test_deflate(self):
        res = self.uri_opener.GET(URL(self.server.url("/deflate.html")), cache=False)

        content_encoding, _ = res.get_headers().iget("content-encoding", "")
        self.assertIn("deflate", content_encoding)
        self.assertIn("View HTTP response headers.", res.get_body())

    def test_get_cookies(self):
        self.assertEqual(len(list(self.uri_opener.get_cookies())), 0)

        self.uri_opener.GET(URL(self.server.url("/set-cookie")), cache=False)

        cookies = list(self.uri_opener.get_cookies())
        self.assertEqual(len(cookies), 1)
        self.assertEqual("127.0.0.1", cookies[0].domain)
        self.assertEqual(("session", "abc123"), (cookies[0].name, cookies[0].value))
