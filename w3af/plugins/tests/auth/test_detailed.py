"""
test_detailed.py

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

import re
import urllib.parse
from typing import ClassVar

from w3af.core.data.kb.knowledge_base import DBKnowledgeBase
from w3af.core.data.parsers.doc.url import URL
from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest

SESSION_COOKIE = "w3af_session=valid"
VALID_AUTH_VALUE = "passw0rd"


def _is_authenticated(request):
    return SESSION_COOKIE in (request.headers.get("Cookie") or "")


def _detailed_login_post(mock_response, request, uri, response_headers):
    response_headers["content-type"] = "text/html"
    password = request.parsed_body.get("password", [""])[0]
    if password == VALID_AUTH_VALUE:
        response_headers["Set-Cookie"] = f"{SESSION_COOKIE}; Path=/"
        return 200, response_headers, "<html><body>Login successful</body></html>"
    return 200, response_headers, "<html><body>Invalid credentials</body></html>"


def _post_auth_xss(mock_response, request, uri, response_headers):
    response_headers["content-type"] = "text/html"

    if not _is_authenticated(request):
        return 200, response_headers, "<html><body>Please login first</body></html>"

    query = urllib.parse.urlsplit(request.uri).query
    text = urllib.parse.parse_qs(query).get("text", [""])[0]

    body = (
        "<html><body>"
        "or read your input"
        '<form action="post_auth_xss.py" method="GET">'
        f'<input name="text" type="text" value="{text}" />'
        "</form>"
        f"{text}"
        "</body></html>"
    )
    return 200, response_headers, body


class TestDetailedBasic(PluginTest):

    target_url = "http://mock/auth/auth_1/"

    auth_url = URL(target_url + "login_form.py")
    check_url = URL(target_url + "post_auth_xss.py")
    check_string = "or read your input"
    data_format = "%u=%U&%p=%P&Login=Login"

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(
            target_url,
            body=(
                "<html><body>"
                '<a href="post_auth_xss.py?text=hello">input</a>'
                "</body></html>"
            ),
            method="GET",
        ),
        MockResponse(str(auth_url), body=_detailed_login_post, method="POST"),
        MockResponse(
            re.compile(r"http://mock/auth/auth_1/post_auth_xss\.py.*"),
            body=_post_auth_xss,
            method="GET",
        ),
    ]

    _run_config: ClassVar[dict] = {
        "target": target_url,
        "plugins": {
            "crawl": (
                PluginConfig(
                    "web_spider",
                    ("only_forward", True, PluginConfig.BOOL),
                    ("ignore_regex", ".*logout.*", PluginConfig.STR),
                ),
            ),
            "audit": (
                PluginConfig(
                    "xss",
                ),
            ),
            "auth": (
                PluginConfig(
                    "detailed",
                    ("username", "user@mail.com", PluginConfig.STR),
                    ("password", "passw0rd", PluginConfig.STR),
                    ("username_field", "username", PluginConfig.STR),
                    ("password_field", "password", PluginConfig.STR),
                    ("data_format", data_format, PluginConfig.STR),
                    ("auth_url", auth_url, PluginConfig.URL),
                    ("method", "POST", PluginConfig.STR),
                    ("check_url", check_url, PluginConfig.URL),
                    ("check_string", check_string, PluginConfig.STR),
                    ("follow_redirects", False, PluginConfig.BOOL),
                ),
            ),
        },
    }

    def test_post_auth_xss(self):
        self._scan(self._run_config["target"], self._run_config["plugins"])

        vulns = self.kb.get("xss", "xss")

        self.assertEqual(len(vulns), 1, vulns)

        vuln = vulns[0]
        self.assertEqual(vuln.get_name(), "Cross site scripting vulnerability")
        self.assertEqual(vuln.get_token_name(), "text")


class TestDetailedFailAuth(PluginTest):
    target_url = "http://mock/auth/auth_1/"

    auth_url = URL(target_url + "login_form.py")
    check_url = URL(target_url + "post_auth_xss.py")
    check_string = "or read your input"
    data_format = "%u=%U&%p=%P&Login=Login"

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(
            target_url,
            body=(
                "<html><body>"
                '<a href="post_auth_xss.py?text=hello">input</a>'
                "</body></html>"
            ),
            method="GET",
        ),
        MockResponse(str(auth_url), body=_detailed_login_post, method="POST"),
        MockResponse(
            re.compile(r"http://mock/auth/auth_1/post_auth_xss\.py.*"),
            body=_post_auth_xss,
            method="GET",
        ),
    ]

    _run_config: ClassVar[dict] = {
        "target": target_url,
        "plugins": {
            "crawl": (
                PluginConfig(
                    "web_spider",
                    ("only_forward", True, PluginConfig.BOOL),
                    ("ignore_regex", ".*logout.*", PluginConfig.STR),
                ),
            ),
            "audit": (
                PluginConfig(
                    "xss",
                ),
            ),
            "auth": (
                PluginConfig(
                    "detailed",
                    ("username", "user@mail.com", PluginConfig.STR),
                    ("password", "invalid-passw0rd", PluginConfig.STR),
                    ("username_field", "username", PluginConfig.STR),
                    ("password_field", "password", PluginConfig.STR),
                    ("data_format", data_format, PluginConfig.STR),
                    ("auth_url", auth_url, PluginConfig.URL),
                    ("method", "POST", PluginConfig.STR),
                    ("check_url", check_url, PluginConfig.URL),
                    ("check_string", check_string, PluginConfig.STR),
                    ("follow_redirects", False, PluginConfig.BOOL),
                ),
            ),
        },
    }

    def test_failed_login_invalid_password(self):
        self._scan(self._run_config["target"], self._run_config["plugins"])

        infos = kb.get("authentication", "error")

        self.assertEqual(len(infos), 1)
        info = infos[0]

        expected_desc = (
            "The `detailed` authentication plugin was never able to"
            " authenticate and get a valid application session using the"
            " user-provided configuration settings\n"
            "\n"
            "The following are the last log messages from the authentication"
            " plugin:\n"
            "\n"
            " - Logging into the application with user: user@mail.com\n"
            " - Checking if session for user user@mail.com is active\n"
            ' - User "user@mail.com" is NOT logged into the application, the'
            " `check_string` was not found in the HTTP response with ID 22."
        )

        self.assertEqual(info.get_name(), "Authentication failure")
        self.assertEqual(info.get_desc(with_id=False), expected_desc)
        self.assertEqual(info.get_id(), [21, 22])


class TestDetailedRedirect(PluginTest):

    target_url = "http://mock/auth/"

    auth_url = URL(target_url + "login_form.py")
    check_url = URL(target_url + "verify.py")
    check_string = "Logged in"
    data_format = "%u=%U&%p=%P&Login=Login"

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(
            "http://mock/auth/login_form.py",
            "",
            status=302,
            headers={"Location": "/confirm/?token=123"},
            method="GET",
        ),
        MockResponse(
            "http://mock/confirm/?token=123",
            "Login success",
            status=302,
            headers={"Location": "/auth/home.py"},
        ),
        MockResponse("http://mock/auth/home.py", "Home page"),
        MockResponse("http://mock/auth/verify.py", "Not logged in"),
    ]

    _run_config: ClassVar[dict] = {
        "target": target_url,
        "plugins": {
            "audit": (PluginConfig("xss"),),
            "auth": (
                PluginConfig(
                    "detailed",
                    ("username", "user@mail.com", PluginConfig.STR),
                    ("password", "passw0rd", PluginConfig.STR),
                    ("username_field", "username", PluginConfig.STR),
                    ("password_field", "password", PluginConfig.STR),
                    ("data_format", data_format, PluginConfig.STR),
                    ("auth_url", auth_url, PluginConfig.URL),
                    ("method", "GET", PluginConfig.STR),
                    ("check_url", check_url, PluginConfig.URL),
                    ("check_string", check_string, PluginConfig.STR),
                    ("follow_redirects", True, PluginConfig.BOOL),
                ),
            ),
        },
    }

    def test_redirect_login(self):
        self._scan(self._run_config["target"], self._run_config["plugins"])

        all_paths = set()
        for request in self.received_requests:
            all_paths.add(request.path)

        # Followed two redirects
        self.assertIn("/confirm/?token=123", all_paths)
        self.assertIn("/auth/home.py", all_paths)

        # Send the POST to login
        self.assertIn("/auth/login_form.py", all_paths)


class TestDetailedRedirectLoop(PluginTest):

    target_url = "http://mock/auth/"

    auth_url = URL(target_url + "login_form.py")
    check_url = URL(target_url + "verify.py")
    check_string = "Logged in"
    data_format = "%u=%U&%p=%P&Login=Login"

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(
            "http://mock/auth/login_form.py",
            "",
            status=302,
            headers={"Location": "/confirm/?token=123"},
            method="GET",
        ),
        # Redirect loop #1
        MockResponse(
            "http://mock/confirm/?token=123",
            "Created new token",
            status=302,
            headers={"Location": "/confirm/?token=abc"},
        ),
        # Redirect loop #2
        MockResponse(
            "http://mock/confirm/?token=abc",
            "Token is not new",
            status=302,
            headers={"Location": "/confirm/?token=123"},
        ),
        MockResponse("http://mock/auth/home.py", "Home page"),
        MockResponse("http://mock/auth/verify.py", "Not logged in"),
    ]

    _run_config: ClassVar[dict] = {
        "target": target_url,
        "plugins": {
            "audit": (PluginConfig("xss"),),
            "auth": (
                PluginConfig(
                    "detailed",
                    ("username", "user@mail.com", PluginConfig.STR),
                    ("password", "passw0rd", PluginConfig.STR),
                    ("username_field", "username", PluginConfig.STR),
                    ("password_field", "password", PluginConfig.STR),
                    ("data_format", data_format, PluginConfig.STR),
                    ("auth_url", auth_url, PluginConfig.URL),
                    ("method", "GET", PluginConfig.STR),
                    ("check_url", check_url, PluginConfig.URL),
                    ("check_string", check_string, PluginConfig.STR),
                    ("follow_redirects", True, PluginConfig.BOOL),
                ),
            ),
        },
    }

    def test_redirect_loop_in_login(self):
        """
        The main test here is that the plugin finishes
        """
        self._scan(self._run_config["target"], self._run_config["plugins"])

        all_paths = set()
        for request in self.received_requests:
            all_paths.add(request.path)

        # Followed two redirects which are in a loop
        self.assertIn("/confirm/?token=123", all_paths)
        self.assertIn("/confirm/?token=abc", all_paths)

        # Send the POST to login
        self.assertIn("/auth/login_form.py", all_paths)


class TestDetailedSquareBrackets(PluginTest):
    """
    :see: https://github.com/andresriancho/w3af/issues/5593
    """

    target_url = "http://mock/auth/"

    auth_url = URL("http://mock/auth/auth_2/square_bracket_login_form.py")
    check_url = URL("http://mock/auth/auth_1/post_auth_xss.py")
    check_string = "or read your input"
    data_format = "%u=%U&%p=%P&Login=Login"

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(
            target_url,
            body=(
                "<html><body>"
                '<a href="auth_1/post_auth_xss.py?text=hello">input</a>'
                "</body></html>"
            ),
            method="GET",
        ),
        MockResponse(str(auth_url), body=_detailed_login_post, method="POST"),
        MockResponse(
            re.compile(r"http://mock/auth/auth_1/post_auth_xss\.py.*"),
            body=_post_auth_xss,
            method="GET",
        ),
    ]

    _run_config: ClassVar[dict] = {
        "target": target_url,
        "plugins": {
            "crawl": (
                PluginConfig(
                    "web_spider",
                    ("only_forward", True, PluginConfig.BOOL),
                    ("ignore_regex", ".*logout.*", PluginConfig.STR),
                ),
            ),
            "audit": (
                PluginConfig(
                    "xss",
                ),
            ),
            "auth": (
                PluginConfig(
                    "detailed",
                    ("username", "user@mail.com", PluginConfig.STR),
                    ("password", "passw0rd", PluginConfig.STR),
                    # Check this foo[user] setting! This is what we
                    # want to test
                    ("username_field", "foo[user]", PluginConfig.STR),
                    ("password_field", "password", PluginConfig.STR),
                    ("data_format", data_format, PluginConfig.STR),
                    ("auth_url", auth_url, PluginConfig.URL),
                    ("method", "POST", PluginConfig.STR),
                    ("check_url", check_url, PluginConfig.URL),
                    ("check_string", check_string, PluginConfig.STR),
                    ("follow_redirects", False, PluginConfig.BOOL),
                ),
            ),
        },
    }

    def test_post_auth_xss(self):
        self._scan(self._run_config["target"], self._run_config["plugins"])

        vulns = self.kb.get("xss", "xss")

        self.assertEqual(len(vulns), 1, vulns)

        vuln = vulns[0]
        self.assertEqual(vuln.get_name(), "Cross site scripting vulnerability")
        self.assertEqual(vuln.get_token_name(), "text")


kb = DBKnowledgeBase()
