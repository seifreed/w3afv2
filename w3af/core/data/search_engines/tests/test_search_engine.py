"""
test_search_engine.py

Copyright 2026 w3af contributors

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

from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.search_engines.bing import BingResult
from w3af.core.data.search_engines.search_engine import SearchEngine
from w3af.core.exceptions import BaseFrameworkException


def result(name):
    return BingResult(URL(f"http://w3af.org/{name}"))


class PagedEngine(SearchEngine):
    """
    A search engine over an in-memory corpus, used to verify the paging
    logic implemented by SearchEngine.
    """

    def __init__(self, corpus, error=None):
        super().__init__()
        self.corpus = corpus
        self.error = error
        self.calls = []

    def search(self, query, start, count=10):
        self.calls.append((query, start, count))
        if self.error is not None:
            raise self.error
        return self.corpus[start : start + count]

    def page_search(self, query, start, count=10):
        return self.search(query, start, count)


class TestSearchEngine(unittest.TestCase):

    def test_default_user_agent(self):
        self.assertIn("Mozilla/5.0", SearchEngine()._headers["User-Agent"])

    def test_abstract_methods(self):
        engine = SearchEngine()

        self.assertRaises(NotImplementedError, engine.search, "q", 0)
        self.assertRaises(NotImplementedError, engine.page_search, "q", 0)

    def test_get_n_results_pages_until_the_limit(self):
        engine = PagedEngine([result(i) for i in range(50)])

        results = engine.get_n_results("q", 25)

        self.assertEqual(len(results), 30)
        self.assertEqual([start for _, start, _ in engine.calls], [0, 10, 20])

    def test_get_n_results_stops_without_new_results(self):
        engine = PagedEngine([result("only")] * 30)

        self.assertEqual(engine.get_n_results("q", 100), {result("only")})
        self.assertEqual(len(engine.calls), 2)

    def test_get_n_results_framework_error_is_raised(self):
        engine = PagedEngine([], error=BaseFrameworkException("blocked"))

        with self.assertRaisesRegex(BaseFrameworkException, "blocked"):
            engine.get_n_results("q", 10)

    def test_get_n_results_unexpected_error_is_wrapped(self):
        engine = PagedEngine([], error=KeyError("boom"))

        with self.assertRaises(BaseFrameworkException) as context:
            engine.get_n_results("q", 10)

        self.assertIn("unhandled exception", str(context.exception))
        self.assertIsInstance(context.exception.__cause__, KeyError)

    def test_get_n_result_pages(self):
        engine = PagedEngine([f"page-{i}" for i in range(50)])

        pages = engine.get_n_result_pages("q", 20)

        self.assertEqual(pages, [f"page-{i}" for i in range(20)])

    def test_get_n_result_pages_errors_are_raised(self):
        for error in (BaseFrameworkException("blocked"), KeyError("boom")):
            engine = PagedEngine([], error=error)
            self.assertRaises(type(error), engine.get_n_result_pages, "q", 10)
