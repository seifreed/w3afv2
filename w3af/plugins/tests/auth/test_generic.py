"""
test_generic.py

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
from unittest import SkipTest

import pytest

from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.url.exceptions import (
    ConnectionPoolException,
    HTTPRequestException,
)
from w3af.core.data.url.extended_urllib import ExtendedUrllib
from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest

SESSION_COOKIE = "w3af_session=valid"


def _is_authenticated(request):
    return SESSION_COOKIE in (request.headers.get("Cookie") or "")


def _login_post(mock_response, request, uri, response_headers):
    response_headers["content-type"] = "text/html"
    response_headers["Set-Cookie"] = f"{SESSION_COOKIE}; Path=/"
    return 200, response_headers, "<html><body>Login successful</body></html>"


def _post_auth_xss(mock_response, request, uri, response_headers):
    response_headers["content-type"] = "text/html"

    if not _is_authenticated(request):
        return 200, response_headers, "<html><body>Please login first</body></html>"

    query = urllib.parse.urlsplit(request.uri).query
    text = urllib.parse.parse_qs(query).get("text", [""])[0]

    body = (
        "<html><body>"
        "read your input"
        '<form action="post_auth_xss.py" method="GET">'
        f'<input name="text" type="text" value="{text}" />'
        "</form>"
        f"{text}"
        "</body></html>"
    )
    return 200, response_headers, body


class TestGeneric(PluginTest):

    base_url = "http://mock/auth/auth_1/"
    target_url = base_url
    demo_testfire = "http://demo.testfire.net/bank/"

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(
            base_url,
            body=(
                "<html><body>"
                '<a href="post_auth_xss.py?text=hello">input</a>'
                "</body></html>"
            ),
            method="GET",
        ),
        MockResponse(base_url + "login_form.py", body=_login_post, method="POST"),
        MockResponse(
            re.compile(r"http://mock/auth/auth_1/post_auth_xss\.py.*"),
            body=_post_auth_xss,
            method="GET",
        ),
    ]

    _run_config: ClassVar[dict] = {
        "target": base_url,
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
                    "generic",
                    ("username", "user@mail.com", PluginConfig.STR),
                    ("password", "passw0rd", PluginConfig.STR),
                    ("username_field", "username", PluginConfig.STR),
                    ("password_field", "password", PluginConfig.STR),
                    ("auth_url", URL(base_url + "login_form.py"), PluginConfig.URL),
                    ("check_url", URL(base_url + "post_auth_xss.py"), PluginConfig.URL),
                    ("check_string", "read your input", PluginConfig.STR),
                ),
            ),
        },
    }

    demo_testfire_net: ClassVar[dict] = {
        "target": demo_testfire,
        "plugins": {
            "crawl": (
                PluginConfig(
                    "web_spider",
                    ("only_forward", True, PluginConfig.BOOL),
                    ("ignore_regex", ".*logout.*", PluginConfig.STR),
                    ("follow_regex", ".*queryxpath.*", PluginConfig.STR),
                ),
            ),
            "auth": (
                PluginConfig(
                    "generic",
                    ("username", "admin", PluginConfig.STR),
                    ("password", "admin", PluginConfig.STR),
                    ("username_field", "uid", PluginConfig.STR),
                    ("password_field", "passw", PluginConfig.STR),
                    ("auth_url", URL(demo_testfire + "login.aspx"), PluginConfig.URL),
                    ("check_url", URL(demo_testfire + "main.aspx"), PluginConfig.URL),
                    ("check_string", "View Recent Transactions", PluginConfig.STR),
                ),
            ),
        },
    }

    @pytest.mark.smoke
    def test_post_auth_xss(self):
        self._scan(self._run_config["target"], self._run_config["plugins"])

        vulns = self.kb.get("xss", "xss")

        self.assertEqual(len(vulns), 1, vulns)

        vuln = vulns[0]
        self.assertEqual(vuln.get_name(), "Cross site scripting vulnerability")
        self.assertEqual(vuln.get_token_name(), "text")
        self.assertEqual(vuln.get_url().get_path(), "/auth/auth_1/post_auth_xss.py")

    @pytest.mark.internet
    @pytest.mark.fails
    def test_demo_testfire_net(self):
        # We don't control the demo.testfire.net domain, so we'll check if its
        # up before doing anything else
        uri_opener = ExtendedUrllib()
        login_url = URL(self.demo_testfire + "login.aspx")
        try:
            res = uri_opener.GET(login_url)
        except (HTTPRequestException, ConnectionPoolException) as e:
            raise SkipTest("demo.testfire.net is unreachable!") from e
        else:
            if not "Online Banking Login" in res.body:
                raise SkipTest("demo.testfire.net has changed!")

        self._scan(self.demo_testfire_net["target"], self.demo_testfire_net["plugins"])

        urls = self.kb.get_all_known_urls()
        url_strings = {str(u) for u in urls}

        self.assertTrue(self.demo_testfire + "queryxpath.aspx" in url_strings)
        self.assertTrue(self.demo_testfire + "queryxpath.aspx.cs" in url_strings)
