"""
test_form_auth.py

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

import os
import random
import re
import urllib.parse
from typing import ClassVar

import pytest

from w3af import ROOT_PATH
from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest

SUCCESS_BODY = "Welcome Mr. Admin, how can I help you today?"
FAILED_BODY = "ACCESS DENIED"


def _submitted_params(request):
    """Return the login parameters, from the POST body or the GET query."""
    params = request.parsed_body
    if params:
        return params
    query = urllib.parse.urlsplit(request.uri).query
    return urllib.parse.parse_qs(query)


def _login_responder(form_html, valid_pass, valid_user=None):
    """
    Build a MockResponse body callable for a self-submitting login form: it
    serves the form when there are no credentials and emulates the login
    result (success/failure) when credentials are submitted.
    """

    def respond(mock_response, request, uri, response_headers):
        response_headers["content-type"] = "text/html"
        params = _submitted_params(request)

        if "password" not in params:
            return 200, response_headers, form_html

        password = params.get("password", [""])[0]
        user = params.get("username", [""])[0]

        password_ok = password == valid_pass
        user_ok = valid_user is None or user == valid_user

        if valid_pass is not None and password_ok and user_ok:
            return 200, response_headers, SUCCESS_BODY

        return 200, response_headers, FAILED_BODY

    return respond


class GenericFormAuthTest(PluginTest):
    BASE_PATH = os.path.join(ROOT_PATH, "plugins", "tests", "bruteforce")

    small_users_negative = os.path.join(BASE_PATH, "small-users-negative.txt")
    small_users_positive = os.path.join(BASE_PATH, "small-users-positive.txt")
    small_passwords = os.path.join(BASE_PATH, "small-passwords.txt")

    basic_config: ClassVar[dict] = {
        "crawl": (
            PluginConfig(
                "web_spider",
                ("only_forward", True, PluginConfig.BOOL),
            ),
        ),
        "bruteforce": (
            PluginConfig(
                "form_auth",
                ("users_file", small_users_positive, PluginConfig.STR),
                ("passwd_file", small_passwords, PluginConfig.INPUT_FILE),
                ("use_profiling", False, PluginConfig.BOOL),
            ),
        ),
    }


def _form_html(action, method, with_username=True):
    username_input = '<input name="username" type="text" />' if with_username else ""
    return (
        f'<form method="{method}" action="{action}">'
        f"{username_input}"
        '<input name="password" type="password" />'
        '<input name="submit" type="submit" />'
        "</form>"
    )


class FormAuthTest(GenericFormAuthTest):

    BASE_PATH = os.path.join(ROOT_PATH, "plugins", "tests", "bruteforce")

    target_post_url = "http://mock/bruteforce/form/guessable_login_form.py"
    target_get_url = "http://mock/bruteforce/form/guessable_login_form_get.py"
    target_password_only_url = "http://mock/bruteforce/form/guessable_pass_only.py"
    target_negative_url = "http://mock/bruteforce/form/impossible.py"

    target_url = target_post_url

    _POST_FORM = _form_html("guessable_login_form.py", "POST")
    _GET_FORM = _form_html("guessable_login_form_get.py", "GET")
    _PASS_ONLY_FORM = _form_html("guessable_pass_only.py", "POST", with_username=False)
    _NEG_FORM = _form_html("impossible.py", "POST")

    MOCK_RESPONSES: ClassVar[list] = [
        # POST login form, valid credentials admin/1234
        MockResponse(target_post_url, body=_POST_FORM, method="GET"),
        MockResponse(
            target_post_url,
            body=_login_responder(_POST_FORM, "1234", valid_user="admin"),
            method="POST",
        ),
        # GET login form, valid credentials admin/admin. A regex is used
        # because the credentials are submitted in the query string.
        MockResponse(
            re.compile(r"http://mock/bruteforce/form/guessable_login_form_get\.py.*"),
            body=_login_responder(_GET_FORM, "admin", valid_user="admin"),
            method="GET",
        ),
        # Password-only form, valid password 1234
        MockResponse(target_password_only_url, body=_PASS_ONLY_FORM, method="GET"),
        MockResponse(
            target_password_only_url,
            body=_login_responder(_PASS_ONLY_FORM, "1234"),
            method="POST",
        ),
        # Impossible form, no valid credentials
        MockResponse(target_negative_url, body=_NEG_FORM, method="GET"),
        MockResponse(
            target_negative_url,
            body=_login_responder(_NEG_FORM, None),
            method="POST",
        ),
    ]

    negative_test: ClassVar[dict] = {
        "crawl": (
            PluginConfig(
                "web_spider",
                ("only_forward", True, PluginConfig.BOOL),
            ),
        ),
        "bruteforce": (
            PluginConfig(
                "form_auth",
                (
                    "users_file",
                    GenericFormAuthTest.small_users_negative,
                    PluginConfig.STR,
                ),
                (
                    "passwd_file",
                    GenericFormAuthTest.small_passwords,
                    PluginConfig.INPUT_FILE,
                ),
                ("use_profiling", False, PluginConfig.BOOL),
            ),
        ),
    }

    @pytest.mark.smoke
    def test_found_credentials_post(self):
        self._scan(self.target_post_url, self.basic_config)

        # Assert the general results
        vulns = self.kb.get("form_auth", "auth")
        self.assertEqual(len(vulns), 1)

        vuln = vulns[0]

        self.assertEqual(vuln.get_name(), "Guessable credentials")
        self.assertEqual(vuln.get_url().url_string, self.target_post_url)
        self.assertEqual(vuln["user"], "admin")
        self.assertEqual(vuln["pass"], "1234")

    def test_found_credentials_get(self):
        self._scan(self.target_get_url, self.basic_config)

        # Assert the general results
        vulns = self.kb.get("form_auth", "auth")
        self.assertEqual(len(vulns), 1)

        vuln = vulns[0]

        self.assertEqual(vuln.get_name(), "Guessable credentials")
        self.assertEqual(vuln.get_url().url_string, self.target_get_url)
        self.assertEqual(vuln["user"], "admin")
        self.assertEqual(vuln["pass"], "admin")

    def test_found_credentials_password_only(self):
        self._scan(self.target_password_only_url, self.basic_config)

        # Assert the general results
        vulns = self.kb.get("form_auth", "auth")
        self.assertEqual(len(vulns), 1, vulns)

        vuln = vulns[0]

        self.assertEqual(vuln.get_name(), "Guessable credentials")
        self.assertEqual(vuln.get_url().url_string, self.target_password_only_url)
        self.assertEqual(vuln["user"], "password-only-form")
        self.assertEqual(vuln["pass"], "1234")

    def test_negative(self):
        self._scan(self.target_negative_url, self.negative_test)

        # Assert the general results
        vulns = self.kb.get("form_auth", "auth")
        self.assertEqual(len(vulns), 0)


class TestFormAuthFailedLoginMatchTrivial(GenericFormAuthTest):

    target_url = "http://w3af.org/"
    login_url = "http://w3af.org/login"

    FORM = (
        '<form method="POST" action="/login">'
        '    <input name="username" type="text" />'
        '    <input name="password" type="password" />'
        '    <input name="submit" type="submit" />'
        "</form>"
    )

    def request_callback(self, request, uri, response_headers):
        response_headers["content-type"] = "text/html"

        username = request.parsed_body.get("username", [""])[0]
        password = request.parsed_body.get("password", [""])[0]

        if username == "admin" and password == "admin":
            body = "Welcome Mr. Admin"
        else:
            body = "Fail"

        return 200, response_headers, body

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(
            url=target_url,
            body=FORM,
            status=200,
            method="GET",
            content_type="text/html",
        ),
        MockResponse(
            url=login_url,
            body=request_callback,
            method="POST",
            content_type="text/html",
            status=200,
        ),
    ]

    def test_found_credentials(self):
        self._scan(self.target_url, self.basic_config)

        # Assert the general results
        vulns = self.kb.get("form_auth", "auth")
        self.assertEqual(len(vulns), 1)

        vuln = vulns[0]

        self.assertEqual(vuln.get_name(), "Guessable credentials")
        self.assertEqual(vuln.get_url().url_string, self.login_url)
        self.assertEqual(vuln["user"], "admin")
        self.assertEqual(vuln["pass"], "admin")


class TestFormAuthFailedLoginMatchWithStaticLargeResponse(GenericFormAuthTest):

    target_url = "http://w3af.org/"
    login_url = "http://w3af.org/login"

    FORM = (
        '<form method="POST" action="/login">'
        '    <input name="username" type="text" />'
        '    <input name="password" type="password" />'
        '    <input name="submit" type="submit" />'
        "</form>"
    )

    HEADER = "abc <b>def</b> xyz".join("\n" for _ in range(100))
    FOOTER = "abc <b>def</b> xyz".join("\n" for _ in range(100))

    def request_callback(self, request, uri, response_headers):
        response_headers["content-type"] = "text/html"

        username = request.parsed_body.get("username", [""])[0]
        password = request.parsed_body.get("password", [""])[0]

        klass = TestFormAuthFailedLoginMatchWithStaticLargeResponse

        if username == "admin" and password == "admin":
            body = "{}\n{}\n{}".format(
                klass.HEADER,
                'Success, redirecting to the home page... <a href="/home">home<a>',
                klass.FOOTER,
            )
        else:
            body = klass.HEADER + "\nFail\n" + klass.FOOTER

        return 200, response_headers, body

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(
            url=target_url,
            body=FORM,
            status=200,
            method="GET",
            content_type="text/html",
        ),
        MockResponse(
            url=login_url,
            body=request_callback,
            method="POST",
            content_type="text/html",
            status=200,
        ),
    ]

    def test_found_credentials(self):
        self._scan(self.target_url, self.basic_config)

        # Assert the general results
        vulns = self.kb.get("form_auth", "auth")
        self.assertEqual(len(vulns), 1)

        vuln = vulns[0]

        self.assertEqual(vuln.get_name(), "Guessable credentials")
        self.assertEqual(vuln.get_url().url_string, self.login_url)
        self.assertEqual(vuln["user"], "admin")
        self.assertEqual(vuln["pass"], "admin")


class TestFormAuthFailedLoginMatchWithLargeRandomFailedResponse(GenericFormAuthTest):

    target_url = "http://w3af.org/"
    login_url = "http://w3af.org/login"

    FORM = (
        '<form method="POST" action="/login">'
        '    <input name="username" type="text" />'
        '    <input name="password" type="password" />'
        '    <input name="submit" type="submit" />'
        "</form>"
    )

    HEADER = "abc <b>def</b> xyz".join("\n" for _ in range(100))
    FOOTER = "abc <b>def</b> xyz".join("\n" for _ in range(100))

    def request_callback(self, request, uri, response_headers):
        response_headers["content-type"] = "text/html"

        username = request.parsed_body.get("username", [""])[0]
        password = request.parsed_body.get("password", [""])[0]

        klass = TestFormAuthFailedLoginMatchWithLargeRandomFailedResponse

        if username == "admin" and password == "admin":
            body = "{}\n{}\n{}".format(
                klass.HEADER,
                'Success, redirecting to the home page... <a href="/home">home<a>',
                klass.FOOTER,
            )
        else:
            body = "{}\n{}\n{}".format(
                klass.HEADER,
                f"Invalid username / password {random.randint(1, 10000)}",
                klass.FOOTER,
            )

        return 200, response_headers, body

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(
            url=target_url,
            body=FORM,
            status=200,
            method="GET",
            content_type="text/html",
        ),
        MockResponse(
            url=login_url,
            body=request_callback,
            method="POST",
            content_type="text/html",
            status=200,
        ),
    ]

    def test_found_credentials(self):
        # Controls the numbers generated in the request_callback
        random.seed(1)

        self._scan(self.target_url, self.basic_config)

        # Assert the general results
        vulns = self.kb.get("form_auth", "auth")
        self.assertEqual(len(vulns), 1)

        vuln = vulns[0]

        self.assertEqual(vuln.get_name(), "Guessable credentials")
        self.assertEqual(vuln.get_url().url_string, self.login_url)
        self.assertEqual(vuln["user"], "admin")
        self.assertEqual(vuln["pass"], "admin")


class TestFormAuthFailedLoginMatchWithLargeRandomFailedResponseShortSuccess(
    GenericFormAuthTest
):

    target_url = "http://w3af.org/"
    login_url = "http://w3af.org/login"

    FORM = (
        '<form method="POST" action="/login">'
        '    <input name="username" type="text" />'
        '    <input name="password" type="password" />'
        '    <input name="submit" type="submit" />'
        "</form>"
    )

    HEADER = "abc <b>def</b> xyz".join("\n" for _ in range(100))
    FOOTER = "abc <b>def</b> xyz".join("\n" for _ in range(100))

    def request_callback(self, request, uri, response_headers):
        response_headers["content-type"] = "text/html"

        username = request.parsed_body.get("username", [""])[0]
        password = request.parsed_body.get("password", [""])[0]

        klass = TestFormAuthFailedLoginMatchWithLargeRandomFailedResponse

        if username == "admin" and password == "admin":
            body = "Success, redirecting"
        else:
            body = "{}\n{}\n{}".format(
                klass.HEADER,
                f"Invalid username / password {random.randint(1, 10000)}",
                klass.FOOTER,
            )

        return 200, response_headers, body

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(
            url=target_url,
            body=FORM,
            status=200,
            method="GET",
            content_type="text/html",
        ),
        MockResponse(
            url=login_url,
            body=request_callback,
            method="POST",
            content_type="text/html",
            status=200,
        ),
    ]

    def test_found_credentials(self):
        # Controls the numbers generated in the request_callback
        random.seed(1)

        self._scan(self.target_url, self.basic_config)

        # Assert the general results
        vulns = self.kb.get("form_auth", "auth")
        self.assertEqual(len(vulns), 1)

        vuln = vulns[0]

        self.assertEqual(vuln.get_name(), "Guessable credentials")
        self.assertEqual(vuln.get_url().url_string, self.login_url)
        self.assertEqual(vuln["user"], "admin")
        self.assertEqual(vuln["pass"], "admin")


captcha_count = 1


class TestFormAuthFailedLoginMatchWithCAPTCHA(GenericFormAuthTest):

    target_url = "http://w3af.org/"
    login_url = "http://w3af.org/login"

    FORM = (
        '<form method="POST" action="/login">'
        '    <input name="username" type="text" />'
        '    <input name="password" type="password" />'
        '    <input name="submit" type="submit" />'
        "</form>"
    )

    HEADER = "abc <b>def</b> xyz".join("\n" for _ in range(100))
    FOOTER = "abc <b>def</b> xyz".join("\n" for _ in range(100))

    def request_callback(self, request, uri, response_headers):
        response_headers["content-type"] = "text/html"

        username = request.parsed_body.get("username", [""])[0]
        password = request.parsed_body.get("password", [""])[0]

        klass = TestFormAuthFailedLoginMatchWithLargeRandomFailedResponse

        body = "{}\n{}\n{}".format(
            klass.HEADER,
            f"Invalid username / password {random.randint(1, 10000)}",
            klass.FOOTER,
        )

        if username == "admin":
            global captcha_count
            captcha_count += 1

            if captcha_count > 2:
                body = "{}\n{}\n{}".format(
                    klass.HEADER,
                    f"Now you need to complete a CAPTCHA {random.randint(1, 10000)}",
                    klass.FOOTER,
                )
            else:
                if password == "will-not-guess-not-in-password-file":
                    body = "Success, redirecting"

        return 200, response_headers, body

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(
            url=target_url,
            body=FORM,
            status=200,
            method="GET",
            content_type="text/html",
        ),
        MockResponse(
            url=login_url,
            body=request_callback,
            method="POST",
            content_type="text/html",
            status=200,
        ),
    ]

    def test_not_found_credentials(self):
        # Controls the numbers generated in the request_callback
        random.seed(1)

        self._scan(self.target_url, self.basic_config)

        # Assert the general results
        vulns = self.kb.get("form_auth", "auth")
        self.assertEqual(len(vulns), 0)
