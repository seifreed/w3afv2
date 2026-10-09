"""
test_google.py

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

import json
import unittest
import urllib.parse

from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.search_engines.google import (
    FINISHED_BAD,
    FINISHED_OK,
    IS_NEW,
    GAjaxSearch,
    GMobileSearch,
    GoogleResult,
    GStandardSearch,
    google,
)
from w3af.core.data.search_engines.tests.fixture_proxy import (
    DROP_CONNECTION,
    FixtureProxy,
)
from w3af.core.data.url.http_response import HTTPResponse

SORRY = "Our systems have detected unusual traffic from your network"
PAGES_WITH_MORE_RESULTS = 2


def ajax_page(query, start, size):
    if query == "ajax-broken-json":
        return "this is not json"

    if query == "ajax-denied":
        return json.dumps({"responseStatus": 403, "responseDetails": "quota"})

    results = [{"url": f"http://ajax-{start + i}.com/"} for i in range(size)]
    return json.dumps({"responseStatus": 200, "responseData": {"results": results}})


def html_page(prefix, start, next_page_str):
    links = [
        f"http://{prefix}-{start}.com/",
        f"https://{prefix}-{start}-secure.com/",
        f"ftp://{prefix}-{start}-files.com/",
        f"{prefix}-{start}-no-protocol.com/",
        "",
    ]
    items = "".join(
        f'<h3 class="r"><a href="/url?q={urllib.parse.quote_plus(link)}&amp;sa=U">r</a></h3>'
        for link in links
    )
    more = next_page_str if start // 10 < PAGES_WITH_MORE_RESULTS else ""
    return f"<html><body>{items}{more}</body></html>"


def google_responder(url):
    query = dict(urllib.parse.parse_qsl(url.query))
    q = query["q"]

    if q in ("drop", "ajax-drop"):
        return DROP_CONNECTION

    if url.netloc == "ajax.googleapis.com":
        return ajax_page(q, int(query["start"]), int(query["rsz"]))

    if q == "sorry":
        return f"<html><body>{SORRY}</body></html>"

    if url.path == "/xhtml":
        return html_page("mobile", int(query["start"]), GMobileSearch.NEXT_PAGE_STR)

    return html_page("standard", int(query["start"]), GStandardSearch.NEXT_PAGE_STR)


class GoogleProxyTest(unittest.TestCase):

    def setUp(self):
        self.proxy = FixtureProxy(google_responder)
        self.proxy.__enter__()
        self.addCleanup(self.proxy.__exit__, None, None, None)

        self.uri_opener = self.proxy.opener()
        self.addCleanup(self.uri_opener.end)

    def urls(self, results):
        return [r.URL.url_string for r in results]


class TestGoogle(GoogleProxyTest):

    def test_ajax_results_are_enough(self):
        results = google(self.uri_opener).get_n_results("w3af", 10)

        self.assertEqual(
            self.urls(results), [f"http://ajax-{i}.com/" for i in range(10)]
        )
        self.assertEqual(
            {r.netloc for r in self.proxy.requests}, {"ajax.googleapis.com"}
        )

    def test_falls_back_to_mobile_and_standard_search(self):
        results = google(self.uri_opener).search("ajax-denied", 0, count=10)

        self.assertEqual(
            self.urls(results),
            [
                "http://mobile-0.com/",
                "https://mobile-0-secure.com/",
                "ftp://mobile-0-files.com/",
                "http://mobile-0-no-protocol.com/",
                "http://standard-4.com/",
                "https://standard-4-secure.com/",
                "ftp://standard-4-files.com/",
                "http://standard-4-no-protocol.com/",
            ],
        )

    def test_page_search(self):
        pages = google(self.uri_opener).page_search("w3af", 0, 30)

        self.assertEqual(len(pages), PAGES_WITH_MORE_RESULTS + 1)
        self.assertTrue(all(isinstance(p, HTTPResponse) for p in pages))
        self.assertEqual(
            [
                dict(urllib.parse.parse_qsl(r.query))["start"]
                for r in self.proxy.requests
            ],
            ["0", "10", "20"],
        )

    def test_get_n_result_pages(self):
        pages = google(self.uri_opener).get_n_result_pages("w3af", 20)

        self.assertEqual(len(pages), 2)


class TestGAjaxSearch(GoogleProxyTest):

    def search(self, query, start=0, count=10):
        return GAjaxSearch(self.uri_opener, query, start, count)

    def test_links(self):
        searcher = self.search("w3af", 0, 20)
        self.assertEqual(searcher.status, IS_NEW)

        self.assertEqual(
            self.urls(searcher.links), [f"http://ajax-{i}.com/" for i in range(20)]
        )
        self.assertEqual(searcher.status, FINISHED_OK)
        self.assertEqual(len(searcher.pages), 3)
        self.assertEqual(
            [self.proxy.query(i)["rsz"] for i in range(3)], ["8", "8", "4"]
        )

    def test_start_index_is_capped(self):
        searcher = self.search("w3af", 60, 100)

        self.assertEqual(
            self.urls(searcher.links),
            [
                "http://ajax-60.com/",
                "http://ajax-61.com/",
                "http://ajax-62.com/",
                "http://ajax-63.com/",
            ],
        )

    def test_failures_finish_bad(self):
        for query in ("ajax-broken-json", "ajax-denied", "ajax-drop"):
            searcher = self.search(query)

            self.assertEqual(searcher.links, [])
            self.assertEqual(searcher.status, FINISHED_BAD)

    def test_do_get_requires_url(self):
        searcher = self.search("w3af")

        self.assertRaises(TypeError, searcher._do_GET, "http://w3af.org/")


class TestGStandardSearch(GoogleProxyTest):

    def test_links_and_pages(self):
        searcher = GStandardSearch(self.uri_opener, "w3af", 0, 6)

        links = searcher.links

        self.assertEqual(
            self.urls(links),
            [
                "http://standard-0.com/",
                "https://standard-0-secure.com/",
                "ftp://standard-0-files.com/",
                "http://standard-0-no-protocol.com/",
            ],
        )
        self.assertEqual(len(searcher.pages), 1)
        self.assertEqual(self.proxy.requests[0].path, "/search")

    def test_sorry_page(self):
        searcher = GStandardSearch(self.uri_opener, "sorry", 0, 10)

        self.assertEqual(searcher.links, [])
        self.assertEqual(searcher.status, FINISHED_BAD)


class TestGMobileSearch(GoogleProxyTest):

    def test_links_follow_next_pages(self):
        searcher = GMobileSearch(self.uri_opener, "w3af", 0, 100)

        self.assertEqual(len(searcher.pages), PAGES_WITH_MORE_RESULTS + 1)
        self.assertEqual(len(searcher.links), 4 * (PAGES_WITH_MORE_RESULTS + 1))
        self.assertEqual({r.path for r in self.proxy.requests}, {"/xhtml"})

    def test_sorry_page(self):
        searcher = GMobileSearch(self.uri_opener, "sorry", 0, 10)

        self.assertEqual(searcher.links, [])
        self.assertEqual(searcher.status, FINISHED_BAD)


class TestGoogleResult(unittest.TestCase):

    def test_requires_url(self):
        self.assertRaises(TypeError, GoogleResult, "http://w3af.org/")

    def test_str(self):
        self.assertEqual(str(GoogleResult(URL("http://w3af.org/"))), "http://w3af.org/")
