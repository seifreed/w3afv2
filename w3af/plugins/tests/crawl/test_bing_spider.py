"""
test_bing_spider.py

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

from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.request.fuzzable_request import FuzzableRequest
from w3af.core.data.url.extended_urllib import ExtendedUrllib
from w3af.core.exceptions import BaseFrameworkException
from w3af.plugins.crawl.bing_spider import bing_spider
from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest
from w3af.plugins.tests.search_engine_pages import bing_search_response

# A public IP address target: deciding that it is not a private site does not
# require any DNS query
BASE_URL = "http://8.8.8.8/"

EXPECTED_URLS = (
    "es/education/",
    "en/clients/",
    "services/",
    "research/",
    "blog/",
)


class TestBingSpider(PluginTest):

    target_url = BASE_URL

    MOCK_RESPONSES: ClassVar[list] = [
        bing_search_response([f"{BASE_URL}{path}" for path in EXPECTED_URLS]),
        *[
            MockResponse(f"{BASE_URL}{path}", "Response body.")
            for path in EXPECTED_URLS
        ],
        MockResponse(BASE_URL, "Index"),
    ]

    plugins: ClassVar[dict] = {
        "crawl": (PluginConfig("bing_spider", ("result_limit", 10, PluginConfig.INT)),)
    }

    def test_found_urls(self):
        self._scan(self.target_url, self.plugins)

        urls = {u.url_string for u in self.kb.get_all_known_urls()}
        expected_urls = {BASE_URL} | {BASE_URL + path for path in EXPECTED_URLS}

        self.assertEqual(urls, expected_urls)

        bing_queries = [r.uri for r in self.received_requests if "bing.com" in r.uri]
        self.assertIn(
            "http://www.bing.com/search?q=site%3A8.8.8.8&first=1&FORM=PERE",
            bing_queries,
        )

    def test_private_site_is_not_searched(self):
        plugin = bing_spider()

        with self.assertRaises(BaseFrameworkException):
            plugin.crawl(FuzzableRequest(URL("http://127.0.0.1/")), "debugging-id")

    def test_failed_search_is_ignored(self):
        uri_opener = ExtendedUrllib()
        uri_opener.stop()

        plugin = bing_spider()
        plugin.set_url_opener(uri_opener)
        plugin.crawl(FuzzableRequest(URL(BASE_URL)), "debugging-id")

        self.assertTrue(plugin.output_queue.empty())

    def test_long_description(self):
        self.assertIn("site:domain.com", bing_spider().get_long_desc())
