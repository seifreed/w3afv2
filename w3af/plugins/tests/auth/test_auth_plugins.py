"""
test_auth_plugins.py

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

Unit tests for the auth plugins: each plugin talks, through a real
ExtendedUrllib, to a small local web application served by CannedHTTPServer.
"""

import socket
import unittest

import w3af.core.data.kb.config as cf
import w3af.core.data.kb.knowledge_base as kb
from w3af.core.controllers.exceptions import BaseFrameworkException
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.url.extended_urllib import ExtendedUrllib
from w3af.core.filesystem import create_temp_dir
from w3af.plugins import auth
from w3af.plugins.auth.autocomplete import autocomplete
from w3af.plugins.auth.detailed import detailed
from w3af.plugins.auth.generic import generic
from w3af.plugins.tests.canned_http_server import CannedHTTPServer, CannedReply

USER = "user@mail.com"
AUTH_VALUE = "passw0rd"
SESSION = "session=valid"
CHECK_STRING = "Welcome back"

LOGIN_FORM = (
    '<form action="/login" method="POST">'
    '<input type="text" name="username" />'
    '<input type="password" name="password" />'
    "</form>"
)


def _closed_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


CLOSED_PORT = _closed_port()

PAGES = {
    "/form": LOGIN_FORM,
    "/two-forms": LOGIN_FORM + LOGIN_FORM,
    "/no-login-form": '<form action="/search"><input name="q" /></form>',
    "/other-domain-form": LOGIN_FORM.replace(
        'action="/login"', 'action="http://other.example/login"'
    ),
    "/closed-action-form": LOGIN_FORM.replace(
        'action="/login"', f'action="http://127.0.0.1:{CLOSED_PORT}/login"'
    ),
}


def _respond(request):
    html = {"Content-Type": "text/html"}
    path = request.path.split("?", 1)[0]

    if path == "/login":
        params = request.parsed_body
        if params.get("password", [""])[0] == AUTH_VALUE:
            headers = dict(html, **{"Set-Cookie": f"{SESSION}; Path=/"})
            return CannedReply(200, headers, "Logged in")
        return CannedReply(200, html, "Invalid credentials")

    if path == "/check":
        if SESSION in (request.headers.get("Cookie") or ""):
            return CannedReply(200, html, f"{CHECK_STRING} {USER}")
        return CannedReply(200, html, "Please login")

    if path == "/image":
        return CannedReply(200, {"Content-Type": "image/png"}, b"\x89PNG\r\n")

    if path in PAGES:
        return CannedReply(200, html, f"<html><body>{PAGES[path]}</body></html>")

    return CannedReply(404, html, "Not found")


class AuthPluginTestCase(unittest.TestCase):

    def setUp(self):
        create_temp_dir()
        kb.kb.cleanup()

        previous_blacklist = cf.cf.get("blacklist_audit")
        self.addCleanup(cf.cf.save, "blacklist_audit", previous_blacklist)

        self.server = CannedHTTPServer(_respond)
        self.server.start()
        self.addCleanup(self.server.stop)

        self.uri_opener = ExtendedUrllib()
        self.addCleanup(self.uri_opener.end)

        self.base = f"http://127.0.0.1:{self.server.port}"

    def tearDown(self):
        kb.kb.cleanup()

    def url(self, path, base=None):
        return URL((base or self.base) + path)

    def configure(self, plugin, **values):
        options = plugin.get_options()
        for name, value in values.items():
            options[name].set_value(value)
        plugin.set_options(options)
        plugin.set_url_opener(self.uri_opener)
        return plugin


class TestAuthPackage(unittest.TestCase):
    def test_long_description(self):
        self.assertIn("Auth plugins", auth.get_long_description())


class TestGeneric(AuthPluginTestCase):

    def _plugin(self, password=AUTH_VALUE, auth_base=None):
        return self.configure(
            generic(),
            username=USER,
            password=password,
            username_field="username",
            password_field="password",
            auth_url=self.url("/login", auth_base),
            check_url=self.url("/check"),
            check_string=CHECK_STRING,
        )

    def test_login_success(self):
        plugin = self._plugin()
        self.assertTrue(plugin.login())
        self.assertTrue(plugin.has_active_session())

    def test_login_failure_disables_after_max_attempts(self):
        plugin = self._plugin(password="wrong")

        for _ in range(plugin.MAX_CONSECUTIVE_FAILED_LOGIN_COUNT):
            self.assertFalse(plugin.login())

        self.assertFalse(plugin.login())
        self.assertFalse(plugin.has_active_session())

    def test_login_http_error(self):
        plugin = self._plugin(auth_base=f"http://127.0.0.1:{CLOSED_PORT}")
        self.assertFalse(plugin.login())

    def test_logout(self):
        self.assertIsNone(self._plugin().logout())

    def test_missing_options(self):
        plugin = generic()
        self.assertRaises(
            BaseFrameworkException, plugin.set_options, plugin.get_options()
        )

    def test_long_desc(self):
        self.assertIn("authentication", generic().get_long_desc())


class TestDetailed(AuthPluginTestCase):

    def _plugin(self, password=AUTH_VALUE, auth_base=None):
        return self.configure(
            detailed(),
            username=USER,
            password=password,
            username_field="username",
            password_field="password",
            data_format="%u=%U&%p=%P",
            method="POST",
            auth_url=self.url("/login", auth_base),
            check_url=self.url("/check"),
            check_string=CHECK_STRING,
        )

    def test_login_success(self):
        self.assertTrue(self._plugin().login())

    def test_login_failure_disables_after_max_attempts(self):
        plugin = self._plugin(password="wrong")

        for _ in range(plugin.MAX_CONSECUTIVE_FAILED_LOGIN_COUNT):
            self.assertFalse(plugin.login())

        self.assertFalse(plugin.login())

    def test_login_http_error(self):
        plugin = self._plugin(auth_base=f"http://127.0.0.1:{CLOSED_PORT}")
        self.assertFalse(plugin.login())

    def test_logout(self):
        self.assertIsNone(self._plugin().logout())

    def test_missing_options(self):
        plugin = detailed()
        options = plugin.get_options()
        options["username"].set_value("")
        self.assertRaises(BaseFrameworkException, plugin.set_options, options)

    def test_long_desc(self):
        self.assertIn("authentication", detailed().get_long_desc())


class TestAutocomplete(AuthPluginTestCase):

    def _plugin(self, form_path="/form", password=AUTH_VALUE, form_base=None):
        return self.configure(
            autocomplete(),
            username=USER,
            password=password,
            login_form_url=self.url(form_path, form_base),
            check_url=self.url("/check"),
            check_string=CHECK_STRING,
        )

    def test_login_success(self):
        plugin = self._plugin()
        self.assertTrue(plugin.login())
        self.assertIn(self.url("/login"), cf.cf.get("blacklist_audit"))

    def test_login_success_with_two_login_forms(self):
        self.assertTrue(self._plugin("/two-forms").login())

    def test_wrong_password_fails_session_check(self):
        self.assertFalse(self._plugin(password="wrong").login())

    def test_page_without_login_form(self):
        self.assertFalse(self._plugin("/no-login-form").login())

    def test_login_form_on_other_domain_is_ignored(self):
        self.assertFalse(self._plugin("/other-domain-form").login())

    def test_login_form_url_unreachable(self):
        plugin = self._plugin(form_base=f"http://127.0.0.1:{CLOSED_PORT}")
        self.assertFalse(plugin.login())

    def test_login_form_url_without_parser(self):
        self.assertFalse(self._plugin("/image").login())

    def test_form_submission_error(self):
        self.assertFalse(self._plugin("/closed-action-form").login())

    def test_disabled_after_max_attempts(self):
        plugin = self._plugin("/no-login-form")

        for _ in range(plugin.MAX_CONSECUTIVE_FAILED_LOGIN_COUNT):
            self.assertFalse(plugin.login())

        self.assertFalse(plugin.login())

    def test_logout(self):
        self.assertIsNone(self._plugin().logout())

    def test_missing_options(self):
        plugin = autocomplete()
        self.assertRaises(
            BaseFrameworkException, plugin.set_options, plugin.get_options()
        )

    def test_long_desc(self):
        self.assertIn("CSRF", autocomplete().get_long_desc())


class TestAuthenticationFailureReport(AuthPluginTestCase):
    """
    After too many consecutive failures every auth plugin reports where the
    authentication failed, which requires the main authentication URL.
    """

    def test_generic_reports_auth_url(self):
        plugin = self.configure(
            generic(),
            username=USER,
            password="wrong",
            username_field="username",
            password_field="password",
            auth_url=self.url("/login"),
            check_url=self.url("/check"),
            check_string=CHECK_STRING,
        )

        for _ in range(plugin.MAX_CONSECUTIVE_FAILED_LOGIN_COUNT):
            plugin.login()

        errors = kb.kb.get("authentication", "error")
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].get_uri(), self.url("/login"))
