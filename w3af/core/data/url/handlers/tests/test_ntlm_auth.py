"""
test_ntlm_auth.py

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

import base64
import os
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path

import spnego
from spnego.exceptions import SpnegoError

from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.url import opener_settings
from w3af.core.data.url.director import CustomOpenerDirector, build_opener
from w3af.core.data.url.handlers.keepalive import HTTPHandler
from w3af.core.data.url.handlers.ntlm_auth import HTTPNtlmAuthHandler
from w3af.core.data.url.handlers.tests.local_server import LocalServer, Reply
from w3af.core.data.url.http_request import HTTPRequest

NEGOTIATE_MESSAGE = b"\x01\x00\x00\x00"


def b64(token):
    return base64.b64encode(token).decode("ascii")


def ntlm_required(header="NTLM"):
    return Reply(401, "Must authenticate.", headers=[("WWW-Authenticate", header)])


class NTLMServer:
    """
    Answers like an IIS site protected with NTLM, validating the credentials
    against the pyspnego NTLM_USER_FILE. When `restart` is True the server
    never accepts the authentication and keeps sending new challenges.
    """

    def __init__(self, restart=False):
        self.restart = restart
        self.negotiate = None
        self.context = None

    def challenge(self):
        self.context = spnego.server(protocol="ntlm")
        return ntlm_required(
            f"Basic realm=w3af, NTLM {b64(self.context.step(self.negotiate))}"
        )

    def __call__(self, request):
        authorization = request.headers.get("Authorization", "")
        if not authorization.startswith("NTLM "):
            return ntlm_required()

        token = base64.b64decode(authorization[5:])
        if token[8:12] == NEGOTIATE_MESSAGE or self.restart:
            self.negotiate = self.negotiate or token
            return self.challenge()

        try:
            self.context.step(token)
        except SpnegoError:
            return ntlm_required()
        return Reply(body=f"You are {self.context.client_principal}")


class TestNTLMHandler(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        users = Path(directory.name, "ntlm_users")
        users.write_text("MOTH:admin:admin\n:local:secret\n")

        previous = os.environ.get("NTLM_USER_FILE")
        os.environ["NTLM_USER_FILE"] = str(users)
        self.addCleanup(self.restore_user_file, previous)

        self.server = LocalServer(
            {
                "/ntlm": NTLMServer(),
                "/restart": NTLMServer(restart=True),
                "/no-header": Reply(401, "Who are you?"),
                "/bad-challenge": ntlm_required("NTLM !!!"),
            }
        ).start()
        self.addCleanup(self.server.stop)

    @staticmethod
    def restore_user_file(previous):
        if previous is None:
            os.environ.pop("NTLM_USER_FILE")
        else:
            os.environ["NTLM_USER_FILE"] = previous

    def open(self, path, user="moth\\admin", password="admin", url=None):
        url = url or self.server.url(path)
        passman = urllib.request.HTTPPasswordMgrWithDefaultRealm()
        passman.add_password(None, url, user, password)
        opener = build_opener(
            CustomOpenerDirector, [HTTPHandler(), HTTPNtlmAuthHandler(passman)]
        )
        return opener.open(HTTPRequest(URL(self.server.url(path))))

    def test_auth_valid_creds(self):
        response = self.open("/ntlm")
        self.assertEqual(response.read(), b"You are moth\\admin")

    def test_auth_valid_creds_without_domain(self):
        response = self.open("/ntlm", user="local", password="secret")
        self.assertTrue(response.read().startswith(b"You are "))

    def test_auth_invalid_creds(self):
        self.assertRaises(
            urllib.error.HTTPError, self.open, "/ntlm", "moth\\invalid", "invalid"
        )

    def test_server_never_accepting_the_authentication(self):
        with self.assertRaisesRegex(urllib.error.HTTPError, "NTLM auth failed"):
            self.open("/restart")

    def test_responses_without_ntlm_challenge(self):
        for path in ("/no-header", "/bad-challenge"):
            with self.assertRaises(urllib.error.HTTPError) as error:
                self.open(path)
            self.assertEqual(error.exception.code, 401)
            error.exception.close()

    def test_no_credentials_for_the_url(self):
        other_url = f"http://localhost:{self.server.port}/"

        with self.assertRaises(urllib.error.HTTPError) as error:
            self.open("/restart", url=other_url)
        self.assertEqual(error.exception.code, 401)
        error.exception.close()

    def test_challenge_without_credentials(self):
        handler = HTTPNtlmAuthHandler()
        request = HTTPRequest(URL(self.server.url("/ntlm")))
        negotiate = spnego.client("user", "pass", protocol="ntlm").step()
        challenge = spnego.server(protocol="ntlm").step(negotiate)
        headers = {"www-authenticate": f"NTLM {b64(challenge)}"}

        self.assertIs(handler.http_request(request), request)
        self.assertIsNone(
            handler.retry_using_http_NTLM_auth(
                request, "www-authenticate", None, headers
            )
        )

    def test_w3af_opener_authenticates(self):
        settings = opener_settings.OpenerSettings()
        settings.set_ntlm_auth(self.server.url("/ntlm"), "moth", "admin", "admin")
        settings.build_openers()

        response = settings.get_custom_opener().open(
            HTTPRequest(URL(self.server.url("/ntlm")))
        )

        self.assertEqual(response.code, 200)
        self.assertEqual(response.read(), b"You are moth\\admin")
