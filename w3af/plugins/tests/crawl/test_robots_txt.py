"""
test_robots_txt.py

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

import unittest
from typing import ClassVar

from w3af.core.data.dc.headers import Headers
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.url.http_response import HTTPResponse
from w3af.plugins.crawl.robots_txt import robots_txt
from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest

ROBOTS_TXT = """# Comment line
User-agent: *

Disallow: /hidden/
Allow: /public/
Crawl-delay: 10
"""

RUN_CONFIG: dict = {"crawl": (PluginConfig("robots_txt"),)}


class TestRobots(PluginTest):

    target_url = "http://mock/"

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(target_url, "index"),
        MockResponse(target_url + "robots.txt", ROBOTS_TXT, content_type="text/plain"),
        MockResponse(target_url + "hidden/", "hidden"),
        MockResponse(target_url + "public/", "public"),
    ]

    def test_robots(self):
        self._scan(self.target_url, RUN_CONFIG)

        urls = set(self.kb.get_all_known_urls())

        expected_urls = {
            URL(self.target_url),
            URL(self.target_url + "hidden/"),
            URL(self.target_url + "public/"),
            URL(self.target_url + "robots.txt"),
        }

        self.assertEqual(urls, expected_urls)

        infos = self.kb.get("robots_txt", "robots.txt")
        self.assertEqual(len(infos), 1, infos)
        self.assertEqual(infos[0].get_url(), URL(self.target_url + "robots.txt"))


class TestRobotsMissing(PluginTest):

    target_url = "http://mock/"

    MOCK_RESPONSES: ClassVar[list] = [MockResponse(target_url, "index")]

    def test_no_robots_file(self):
        self._scan(self.target_url, RUN_CONFIG)

        self.assertEqual(self.kb.get("robots_txt", "robots.txt"), [])


class TestRobotsWithoutEntries(PluginTest):

    target_url = "http://mock/"

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(target_url, "index"),
        MockResponse(
            target_url + "robots.txt",
            "# Only comments here\nUser-agent: *\n",
            content_type="text/plain",
        ),
    ]

    def test_robots_without_entries(self):
        self._scan(self.target_url, RUN_CONFIG)

        self.assertEqual(self.kb.get("robots_txt", "robots.txt"), [])
        self.assertIn(URL(self.target_url + "robots.txt"), self.kb.get_all_known_urls())


class TestRobotsExtractURLs(unittest.TestCase):

    base_url = URL("http://mock/")

    def extract(self, body):
        headers = Headers([("Content-Type", "text/plain")])
        response = HTTPResponse(200, body, headers, self.base_url, self.base_url)
        return robots_txt()._extract_urls(self.base_url, response)

    def test_ignores_invalid_urls(self):
        urls = self.extract("Allow: http://[::1\nDisallow: /ok/\n")

        self.assertEqual(urls, [URL("http://mock/ok/")])

    def test_ignores_allow_without_colon(self):
        self.assertEqual(self.extract("Allow /no-colon/\n"), [])

    def test_long_desc(self):
        self.assertIn("robots.txt", robots_txt().get_long_desc())
