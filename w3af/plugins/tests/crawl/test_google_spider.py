"""
test_google_spider.py

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

import json
from typing import ClassVar

from w3af.core.controllers.exceptions import BaseFrameworkException
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.request.fuzzable_request import FuzzableRequest
from w3af.plugins.crawl.google_spider import google_spider
from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest
from w3af.plugins.tests.search_engine_pages import (
    GOOGLE_AJAX_SEARCH_URL_RE,
    google_search_responses,
)

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

PLUGINS = {
    "crawl": (PluginConfig("google_spider", ("result_limit", 10, PluginConfig.INT)),)
}


class TestGoogleSpider(PluginTest):

    target_url = BASE_URL

    MOCK_RESPONSES: ClassVar[list] = [
        *google_search_responses([f"{BASE_URL}{path}" for path in EXPECTED_URLS]),
        *[
            MockResponse(f"{BASE_URL}{path}", "Response body.")
            for path in EXPECTED_URLS
        ],
        MockResponse(BASE_URL, "Index"),
    ]

    def test_found_urls(self):
        self._scan(self.target_url, PLUGINS)

        urls = {u.url_string for u in self.kb.get_all_known_urls()}
        expected_urls = {BASE_URL} | {BASE_URL + path for path in EXPECTED_URLS}

        self.assertEqual(urls, expected_urls)

    def test_private_site_is_not_searched(self):
        plugin = google_spider()

        with self.assertRaises(BaseFrameworkException):
            plugin.crawl(FuzzableRequest(URL("http://127.0.0.1/")), "debugging-id")

    def test_long_description(self):
        self.assertIn("site:domain.com", google_spider().get_long_desc())


class TestGoogleSpiderEmptyResponseData(PluginTest):
    """
    Google answered the AJAX API search with a successful status but without
    any responseData, the search results can not be extracted and the plugin
    ignores the search.
    """

    target_url = BASE_URL

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(
            GOOGLE_AJAX_SEARCH_URL_RE,
            json.dumps(
                {"responseData": None, "responseDetails": None, "responseStatus": 200}
            ),
            content_type="application/json",
        ),
        MockResponse(BASE_URL, "Index"),
    ]

    def test_no_urls_found(self):
        self._scan(self.target_url, PLUGINS)

        urls = {u.url_string for u in self.kb.get_all_known_urls()}
        self.assertEqual(urls, {BASE_URL})
