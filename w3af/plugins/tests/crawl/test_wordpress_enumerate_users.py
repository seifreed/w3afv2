"""
test_wordpress_enumerate_users.py

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
from typing import ClassVar

from w3af.plugins.crawl.wordpress_enumerate_users import wordpress_enumerate_users
from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest

WORDPRESS_URL = "http://wordpress/"

PLUGINS = {
    "crawl": (
        PluginConfig("wordpress_enumerate_users"),
        PluginConfig("web_spider", ("only_forward", True, PluginConfig.BOOL)),
    )
}


def _author_page(title):
    return f"<html><head><title>{title}</title></head><body>Posts</body></html>"


class TestWordpressEnumerateUsers(PluginTest):

    target_url = WORDPRESS_URL

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(
            WORDPRESS_URL,
            '<html><body>My blog <a href="about/">About</a></body></html>',
        ),
        MockResponse(WORDPRESS_URL + "about/", "<html><body>About me</body></html>"),
        MockResponse(WORDPRESS_URL + "wp-login.php", "<form>Log in</form>"),
        MockResponse(
            WORDPRESS_URL + "?author=1",
            "",
            status=301,
            headers={"Location": WORDPRESS_URL + "author/admin/"},
        ),
        MockResponse(WORDPRESS_URL + "author/admin/", _author_page("admin | Blog")),
        MockResponse(WORDPRESS_URL + "?author=2", _author_page("andres | Blog")),
        MockResponse(WORDPRESS_URL + "?author=3", _author_page("andres | Blog")),
        MockResponse(
            WORDPRESS_URL + "?author=4",
            "",
            status=302,
            headers={"Location": WORDPRESS_URL + "login/"},
        ),
        MockResponse(WORDPRESS_URL + "login/", "<html><body>Login</body></html>"),
    ]

    def test_enumerate_users(self):
        self._scan(self.target_url, PLUGINS)

        infos = self.kb.get("wordpress_enumerate_users", "users")

        user_re = re.compile('WordPress user "(.*?)" found')
        enum_users = [user_re.match(i.get_desc()).group(1) for i in infos]

        self.assertEqual(sorted(enum_users), ["admin", "andres"])


class TestWordpressEnumerateUsersNoWordpress(PluginTest):

    target_url = WORDPRESS_URL

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(WORDPRESS_URL, "<html><body>Not a blog</body></html>"),
    ]

    def test_no_wordpress_installation(self):
        self._scan(self.target_url, PLUGINS)

        self.assertEqual(self.kb.get("wordpress_enumerate_users", "users"), [])
        author_requests = [r for r in self.received_requests if "author" in r.uri]
        self.assertEqual(author_requests, [])


def test_wordpress_enumerate_users_long_desc():
    if "?author=ID" not in wordpress_enumerate_users().get_long_desc():
        raise AssertionError
