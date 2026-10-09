"""
test_bing.py

Copyright 2006 Andres Riancho

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
import urllib.parse

from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.search_engines.bing import BingResult, bing
from w3af.core.data.search_engines.tests.fixture_proxy import FixtureProxy


def bing_link(url):
    return f'<li><h2><a href="{url}" h="ID=SERP,5091.1">title</a></h2></li>'


#
# Each results page is keyed by the "first" query string parameter that bing
# receives. The third page repeats the second one, which is how bing answers
# once there are no more results.
#
RESULT_PAGES = {
    "1": [
        "http://site-1.com/a",
        "https://site-2.com/b",
        "http://msn.com/blacklisted-exact",
        "http://www.msn.com/blacklisted-partial",
        "http://cc.bingj.com/cache.aspx",
        "http://",
    ],
    "11": ["http://site-3.com/c", "http://site-1.com/a"],
    "21": ["http://site-3.com/c"],
}


def serve_results(url):
    query = dict(urllib.parse.parse_qsl(url.query))
    links = [] if query["q"] == "nothing" else RESULT_PAGES.get(query["first"], [])
    return "<html><ol>{}</ol></html>".format("".join(bing_link(u) for u in links))


class TestBing(unittest.TestCase):

    def setUp(self):
        self.proxy = FixtureProxy(serve_results)
        self.proxy.__enter__()
        self.addCleanup(self.proxy.__exit__, None, None, None)

        self.uri_opener = self.proxy.opener()
        self.addCleanup(self.uri_opener.end)
        self.bing_se = bing(self.uri_opener)

    def test_search_filters_blacklisted_and_invalid_urls(self):
        results = self.bing_se.search("big bang theory", 0)

        self.assertEqual(
            {r.URL.url_string for r in results},
            {"http://site-1.com/a", "https://site-2.com/b"},
        )

        request = self.proxy.requests[0]
        self.assertEqual(request.netloc, "www.bing.com")
        self.assertEqual(request.path, "/search")
        self.assertEqual(
            self.proxy.query(),
            {"q": "big bang theory", "first": "1", "FORM": "PERE"},
        )

    def test_get_n_results_stops_when_no_new_results(self):
        results = self.bing_se.get_n_results("big bang theory", 200)

        self.assertEqual(
            {r.URL.url_string for r in results},
            {"http://site-1.com/a", "https://site-2.com/b", "http://site-3.com/c"},
        )
        self.assertEqual(
            [self.proxy.query(i)["first"] for i in range(3)], ["1", "11", "21"]
        )

    def test_get_n_results_stops_at_the_limit(self):
        results = self.bing_se.get_n_results("big bang theory", 2)

        self.assertEqual(len(results), 2)
        self.assertEqual(len(self.proxy.requests), 1)

    def test_get_n_results_without_results(self):
        self.assertEqual(self.bing_se.get_n_results("nothing", 10), set())

    def test_bing_does_not_return_result_pages(self):
        self.assertRaises(NotImplementedError, self.bing_se.page_search, "q", 0)


class TestBingResult(unittest.TestCase):

    def test_requires_url(self):
        self.assertRaises(TypeError, BingResult, "http://w3af.org/")

    def test_equality_and_repr(self):
        url = URL("http://w3af.org/")

        self.assertEqual(BingResult(url), BingResult(URL("http://w3af.org/")))
        self.assertEqual(len({BingResult(url), BingResult(url)}), 1)
        self.assertEqual(repr(BingResult(url)), "<bing result http://w3af.org/>")
