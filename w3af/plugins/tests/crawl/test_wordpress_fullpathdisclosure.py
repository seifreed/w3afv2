"""
test_wordpress_fullpathdisclosure.py

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

from typing import ClassVar

from w3af.plugins.crawl.wordpress_fullpathdisclosure import (
    wordpress_fullpathdisclosure,
)
from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest

WORDPRESS_URL = "http://wordpress/"

FATAL_ERROR = (
    "Fatal error: Call to undefined function get_header() in"
    " /var/www/wordpress/wp-content/themes/twenty/header.php on line 7"
)

PLUGINS = {
    "crawl": (
        PluginConfig("wordpress_fullpathdisclosure"),
        PluginConfig("web_spider", ("only_forward", True, PluginConfig.BOOL)),
    )
}

BLOG_INDEX = (
    "<html><head>"
    f'<link rel="stylesheet" href="{WORDPRESS_URL}wp-content/themes/twenty/style.css">'
    "</head><body>"
    '<a href="?p=1">Hello world</a>'
    "</body></html>"
)


class TestWordpressPathDisclosureInTheme(PluginTest):

    target_url = WORDPRESS_URL

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(WORDPRESS_URL, BLOG_INDEX),
        MockResponse(WORDPRESS_URL + "?p=1", "<html><body>First post</body></html>"),
        MockResponse(WORDPRESS_URL + "wp-login.php", "<form>Log in</form>"),
        MockResponse(
            WORDPRESS_URL + "wp-content/plugins/akismet/akismet.php",
            "Hi there! I'm just a plugin.",
        ),
        MockResponse(
            WORDPRESS_URL + "wp-content/themes/twenty/header.php", FATAL_ERROR
        ),
    ]

    def test_path_disclosure_in_theme_header(self):
        self._scan(self.target_url, PLUGINS)

        infos = self.kb.get("wordpress_fullpathdisclosure", "info")

        self.assertEqual(len(infos), 1, infos)
        info = infos[0]

        self.assertEqual(info.get_name(), "WordPress path disclosure")
        self.assertEqual(
            info.get_url().url_string,
            WORDPRESS_URL + "wp-content/themes/twenty/header.php",
        )


class TestWordpressPathDisclosureInPlugin(PluginTest):

    target_url = WORDPRESS_URL + "blog/index.php"

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(target_url, "<html><body>Blog index</body></html>"),
        MockResponse(WORDPRESS_URL + "blog/wp-login.php", "<form>Log in</form>"),
        MockResponse(
            WORDPRESS_URL + "blog/wp-content/plugins/akismet/akismet.php",
            FATAL_ERROR,
        ),
    ]

    def test_path_disclosure_in_akismet(self):
        self._scan(self.target_url, PLUGINS)

        infos = self.kb.get("wordpress_fullpathdisclosure", "info")

        self.assertEqual(len(infos), 1, infos)
        self.assertEqual(
            infos[0].get_url().url_string,
            WORDPRESS_URL + "blog/wp-content/plugins/akismet/akismet.php",
        )


class TestWordpressPathDisclosureNoWordpress(PluginTest):

    target_url = WORDPRESS_URL

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(WORDPRESS_URL, "<html><body>Static site</body></html>"),
    ]

    def test_no_wordpress_installation(self):
        self._scan(self.target_url, PLUGINS)

        self.assertEqual(self.kb.get("wordpress_fullpathdisclosure", "info"), [])


def test_wordpress_fullpathdisclosure_long_desc():
    if "WordPress" not in wordpress_fullpathdisclosure().get_long_desc():
        raise AssertionError
