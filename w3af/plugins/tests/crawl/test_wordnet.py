"""
test_wordnet.py

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
from w3af.plugins.crawl.wordnet import wordnet
from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest

BASE_URL = "http://mock/crawl/wordnet/"

INDEX = (
    "<html><body>"
    '<a href="blue.html">blue</a>'
    '<a href="show.py?color=blue">show</a>'
    "</body></html>"
)

COLOR_DESCRIPTIONS = {
    "blue": "Blue like the deep ocean water under a clear summer sky",
    "red": "Red is the colour of fire, blood and ripe strawberries in June",
}


def _show_colour(mock_response, request, uri, response_headers):
    query = urllib.parse.urlsplit(uri).query
    colour = urllib.parse.parse_qs(query).get("color", [""])[0]
    body = COLOR_DESCRIPTIONS.get(colour, "This colour is not in our catalogue")
    response_headers["Content-Type"] = "text/html"
    return 200, response_headers, f"<html><body>{body}</body></html>"


class TestWordnet(PluginTest):

    target_url = BASE_URL

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(BASE_URL, INDEX),
        MockResponse(BASE_URL + "blue.html", "The blue page talks about the sea"),
        MockResponse(BASE_URL + "red.html", "Red page: fire trucks and roses"),
        MockResponse(BASE_URL + "green.html", "Green page: grass, frogs, leaves"),
        MockResponse(BASE_URL + "azure.html", "Azure page: cloud computing stuff"),
        MockResponse(BASE_URL + "hide.py", "You found the hidden script output"),
        MockResponse(
            re.compile(re.escape(BASE_URL) + r"show\.py\?.*"), body=_show_colour
        ),
    ]

    _run_configs: ClassVar[dict] = {
        "cfg": {
            "target": target_url,
            "plugins": {
                "crawl": (
                    PluginConfig("wordnet", ("wn_results", 20, PluginConfig.INT)),
                    PluginConfig(
                        "web_spider", ("only_forward", True, PluginConfig.BOOL)
                    ),
                )
            },
        }
    }

    def test_found_urls(self):
        cfg = self._run_configs["cfg"]
        self._scan(cfg["target"], cfg["plugins"])

        expected_urls = (
            "",
            "azure.html",
            "blue.html",
            "green.html",
            "hide.py",
            "red.html",
            "show.py?color=blue",
            "show.py?color=red",
        )

        frs = kb.get_all_known_fuzzable_requests()

        self.assertEqual(
            {fr.get_uri().url_string for fr in frs},
            {(self.target_url + end) for end in expected_urls},
        )


class TestSearchWordnet:
    def test_search_wordnet(self):
        wn = wordnet()
        wn_result = wn._search_wn("blue")

        if len(wn_result) != wn._wordnet_results:
            raise AssertionError
        if "red" not in wn_result:
            raise AssertionError

    def test_search_excludes_the_searched_word(self):
        wn = wordnet()
        wn._wordnet_results = 100

        if "show" in wn._search_wn("show"):
            raise AssertionError

    def test_search_ignores_numbers_and_empty_words(self):
        wn = wordnet()

        if wn._search_wn("") != []:
            raise AssertionError
        if wn._search_wn("1234") != []:
            raise AssertionError

    def test_search_unknown_word(self):
        if wordnet()._search_wn("xyzzyq") != []:
            raise AssertionError

    def test_long_desc(self):
        if "wordnet database" not in wordnet().get_long_desc():
            raise AssertionError


kb = DBKnowledgeBase()
