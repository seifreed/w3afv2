"""
test_digit_sum.py

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
import unittest
import urllib.parse
from typing import ClassVar

from w3af.core.data.dc.urlencoded_form import URLEncodedForm
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.request.fuzzable_request import FuzzableRequest
from w3af.plugins.crawl.digit_sum import digit_sum
from w3af.plugins.tests.helper import LOREM, MockResponse, PluginConfig, PluginTest

BASE_URL = "http://mock/crawl/digit_sum/"

ARTICLES = {
    "21": "<html><body><h1>Gardening</h1><p>" + LOREM + "</p></body></html>",
    "22": (
        "<html><body><h2>Cooking 101</h2>"
        "<ul><li>Boil water</li><li>Add pasta</li><li>Wait ten minutes</li>"
        "<li>Drain and serve with tomato sauce and basil</li></ul>"
        "</body></html>"
    ),
}

OUT_OF_RANGE = "<html><body>There is no article with that id.</body></html>"


def _article(mock_response, request, uri, response_headers):
    query = urllib.parse.urlsplit(request.uri).query
    article_id = urllib.parse.parse_qs(query).get("id", [""])[0]

    response_headers["Content-Type"] = "text/html"
    return 200, response_headers, ARTICLES.get(article_id, OUT_OF_RANGE)


class TestDigitSum(PluginTest):

    target_url = BASE_URL

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(BASE_URL + "index-3-1.html", "<html>Third page</html>"),
        MockResponse(BASE_URL + "index-2-1.html", "<html>Second page</html>"),
        MockResponse(re.compile(re.escape(BASE_URL + "index1.py?")), _article),
    ]

    _run_config: ClassVar[dict] = {
        "target": None,
        "plugins": {"crawl": (PluginConfig("digit_sum"),)},
    }

    def test_found_fname(self):
        self._scan(self.target_url + "index-3-1.html", self._run_config["plugins"])

        EXPECTED_URLS = (
            "/crawl/digit_sum/index-3-1.html",
            "/crawl/digit_sum/index-2-1.html",
        )
        self.assertAllURLsFound(EXPECTED_URLS)

    def test_found_qs(self):
        self._scan(self.target_url + "index1.py?id=22", self._run_config["plugins"])

        EXPECTED_URLS = (
            "/crawl/digit_sum/index1.py?id=20",
            "/crawl/digit_sum/index1.py?id=21",
            "/crawl/digit_sum/index1.py?id=22",
            "/crawl/digit_sum/index1.py?id=23",
        )
        self.assertAllURLsFound(EXPECTED_URLS)


class TestDigitSumUnit(unittest.TestCase):
    def test_post_requests_are_not_mangled(self):
        plugin = digit_sum()
        post_data = URLEncodedForm()
        post_data["id"] = ["1"]
        request = FuzzableRequest(
            URL(BASE_URL + "index1.py"), method="POST", post_data=post_data
        )

        plugin.crawl(request, None)

        self.assertTrue(plugin.output_queue.empty())

    def test_do_combinations(self):
        plugin = digit_sum()

        self.assertEqual(
            plugin._do_combinations("abc123def56"),
            ["abc124def56", "abc122def56", "abc123def57", "abc123def55"],
        )

    def test_too_many_digit_sections_are_not_mangled(self):
        self.assertEqual(digit_sum()._do_combinations("a1b2c3d4e5"), [])

    def test_long_description(self):
        self.assertIn("numbers", digit_sum().get_long_desc())
