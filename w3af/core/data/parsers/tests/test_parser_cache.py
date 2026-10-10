"""
test_parser_cache.py

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

import threading
import unittest

from w3af.core.data.dc.headers import Headers
from w3af.core.data.parsers import parser_cache
from w3af.core.data.parsers.doc.html import HTMLParser
from w3af.core.data.parsers.doc.sgml import Tag
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.parsers.ipc.serialization import DeserializationError
from w3af.core.data.parsers.mp_document_parser import MultiProcessingDocumentParser
from w3af.core.data.parsers.parser_cache import ParserCache
from w3af.core.data.parsers.tests.test_document_parser import _build_http_response
from w3af.core.data.parsers.tests.test_mp_document_parser import (
    HTML_DELAYED,
    HTML_OK,
    MEMORY_LIMIT,
    DelayedParser,
    FailingParser,
    UseMemoryParser,
    _MarkerParser,
)
from w3af.core.data.parsers.utils.response_uniq_id import (
    get_body_unique_id,
    get_response_unique_id,
)
from w3af.core.data.url.http_response import HTTPResponse
from w3af.core.exceptions import BaseFrameworkException, ScanMustStopException


class TestParserCache(unittest.TestCase):

    def setUp(self):
        self.url = URL("http://w3af.com")
        self.headers = Headers([("content-type", "text/html")])
        self.dpc = ParserCache()

    def tearDown(self):
        self.dpc.clear()

    def test_basic(self):
        resp1 = HTTPResponse(200, "abc", self.headers, self.url, self.url)
        resp2 = HTTPResponse(200, "abc", self.headers, self.url, self.url)

        parser1 = self.dpc.get_document_parser_for(resp1)
        parser2 = self.dpc.get_document_parser_for(resp2)

        self.assertEqual(id(parser1), id(parser2))

    def test_bug_13_Dec_2012(self):
        url1 = URL("http://w3af.com/foo/")
        url2 = URL("http://w3af.com/bar/")
        body = '<a href="?id=1">1</a>'
        resp1 = HTTPResponse(200, body, self.headers, url1, url1)
        resp2 = HTTPResponse(200, body, self.headers, url2, url2)

        parser1 = self.dpc.get_document_parser_for(resp1)
        parser2 = self.dpc.get_document_parser_for(resp2)

        self.assertNotEqual(id(parser1), id(parser2))

        _, parsed_refs_1 = parser1.get_references()
        _, parsed_refs_2 = parser2.get_references()

        self.assertEqual(parsed_refs_1, parsed_refs_2)

    def test_issue_188_invalid_url(self):
        # https://github.com/andresriancho/w3af/issues/188
        all_chars = "".join([chr(i) for i in range(255)])
        response = HTTPResponse(200, all_chars, self.headers, self.url, self.url)
        self.dpc.get_document_parser_for(response)

    def test_blacklisted_response_is_not_parsed_again(self):
        http_resp = _build_http_response("<html>blacklisted</html>", "text/html")
        hash_string = get_response_unique_id(http_resp)
        self.dpc.add_to_blacklist(hash_string)

        with self.assertRaisesRegex(
            BaseFrameworkException, "Exceeded timeout while parsing"
        ):
            self.dpc.get_document_parser_for(http_resp)

    def test_get_tags_by_filter_simple(self):
        html = '<a href="/def">abc</a>'
        resp1 = HTTPResponse(200, html, self.headers, self.url, self.url)
        resp2 = HTTPResponse(200, html, self.headers, self.url, self.url)

        parser1 = self.dpc.get_tags_by_filter(resp1, tags=("a",))
        parser2 = self.dpc.get_tags_by_filter(resp2, tags=("a",))

        self.assertEqual(id(parser1), id(parser2))

    def test_get_tags_by_filter_different_tags(self):
        html = '<a href="/def">abc</a><b>hello</b>'
        resp1 = HTTPResponse(200, html, self.headers, self.url, self.url)
        resp2 = HTTPResponse(200, html, self.headers, self.url, self.url)

        parser1 = self.dpc.get_tags_by_filter(resp1, tags=("a",))
        parser2 = self.dpc.get_tags_by_filter(resp2, tags=("b",))

        self.assertNotEqual(id(parser1), id(parser2))


class TestParserCacheWithWorkerFailures(unittest.TestCase):
    """
    Drive ParserCache through a real MultiProcessingDocumentParser configured
    with parsers that time out, exhaust memory or fail.
    """

    def setUp(self):
        self.mp_parser = MultiProcessingDocumentParser(
            parser_timeout=2,
            max_workers=1,
            memory_limit=MEMORY_LIMIT,
            parsers=(
                DelayedParser,
                UseMemoryParser,
                FailingParser,
                UnloadableParser,
                BadTagsParser,
                HTMLParser,
            ),
        )
        self.dpc = ParserCache(mp_parser=self.mp_parser)

    def tearDown(self):
        self.dpc.clear()

    def blacklisted(self, http_resp):
        return get_response_unique_id(http_resp) in self.dpc._parser_blacklist

    def test_timeout_blacklists_the_response(self):
        http_resp = _build_http_response(HTML_DELAYED % "", "text/html")

        with self.assertRaisesRegex(BaseFrameworkException, "Reached timeout"):
            self.dpc.get_document_parser_for(http_resp)

        self.assertTrue(self.blacklisted(http_resp))

    def test_memory_limit_blacklists_the_response(self):
        http_resp = _build_http_response("<html>UseMemoryParser!</html>", "text/html")

        with self.assertRaisesRegex(BaseFrameworkException, "memory usage limit"):
            self.dpc.get_document_parser_for(http_resp)

        self.assertTrue(self.blacklisted(http_resp))

    def test_parsing_error(self):
        http_resp = _build_http_response("<html>FailingParser!</html>", "text/html")

        with self.assertRaisesRegex(BaseFrameworkException, "There is no parser"):
            self.dpc.get_document_parser_for(http_resp)

        self.assertFalse(self.blacklisted(http_resp))

    def test_unloadable_parser(self):
        http_resp = _build_http_response("<html>UnloadableParser!</html>", "text/html")

        with self.assertRaises(BaseFrameworkException) as context:
            self.dpc.get_document_parser_for(http_resp)

        self.assertIsInstance(context.exception.__cause__, DeserializationError)

    def test_unloadable_tags(self):
        http_resp = _build_http_response("<html>BadTagsParser!</html>", "text/html")

        with self.assertRaisesRegex(BaseFrameworkException, "Unhandled exception"):
            self.dpc.get_tags_by_filter(http_resp, ("html",))

    def test_stopped_pool(self):
        pool = self.mp_parser.start_workers()
        pool.stop()
        pool.join()

        http_resp = _build_http_response(HTML_OK % "", "text/html")

        with self.assertRaisesRegex(ScanMustStopException, "invalid state"):
            self.dpc.get_document_parser_for(http_resp)

        with self.assertRaisesRegex(ScanMustStopException, "invalid state"):
            self.dpc.get_tags_by_filter(http_resp, ("a",))


class TestParserCacheConcurrentRequests(unittest.TestCase):
    """
    When another thread is already parsing a response, ParserCache waits for
    the event that thread registered in _parser_finished_events.
    """

    def setUp(self):
        self.mp_parser = MultiProcessingDocumentParser(parser_timeout=0.2)
        self.dpc = ParserCache(mp_parser=self.mp_parser)
        self.http_resp = _build_http_response(HTML_OK % "", "text/html")

    def tearDown(self):
        self.dpc.clear()

    def register_parsing(self, hash_string, finished):
        event = threading.Event()
        if finished:
            event.set()
        self.dpc._parser_finished_events[hash_string] = event

    def tags_hash(self, tags, yield_text=False):
        return get_body_unique_id(self.http_resp, prepend=f"{tags!r}{yield_text!r}")

    def test_parser_waits_for_finished_parse(self):
        self.register_parsing(get_response_unique_id(self.http_resp), finished=True)
        self.mp_parser.parser_timeout = 60

        parser = self.dpc.get_document_parser_for(self.http_resp)

        self.assertIsInstance(parser.get_parser(), HTMLParser)

    def test_parser_wait_times_out(self):
        self.register_parsing(get_response_unique_id(self.http_resp), finished=False)

        with self.assertRaisesRegex(BaseFrameworkException, "Waited more than"):
            self.dpc.get_document_parser_for(self.http_resp)

    def test_tags_wait_for_finished_parse(self):
        self.register_parsing(self.tags_hash(("a",)), finished=True)
        self.mp_parser.parser_timeout = 60

        tags = self.dpc.get_tags_by_filter(self.http_resp, ("a",))

        self.assertEqual(tags, [Tag("a", {"href": "/abc"}, None)])

    def test_tags_wait_times_out(self):
        self.register_parsing(self.tags_hash(("a",)), finished=False)

        self.assertEqual(self.dpc.get_tags_by_filter(self.http_resp, ("a",)), [])


class TestParserCacheBehaviour(unittest.TestCase):

    def setUp(self):
        self.dpc = ParserCache()
        self.http_resp = _build_http_response(HTML_OK % "", "text/html")

    def tearDown(self):
        self.dpc.clear()

    def test_can_parse_is_cached(self):
        self.assertTrue(self.dpc.can_parse(self.http_resp))
        self.assertTrue(self.dpc.can_parse(self.http_resp))
        self.assertEqual(len(self.dpc._can_parse_cache), 1)

    def test_should_cache(self):
        self.assertTrue(self.dpc.should_cache(self.http_resp))

        body = "A" * ParserCache.MAX_CACHEABLE_BODY_LEN
        self.assertFalse(self.dpc.should_cache(_build_http_response(body, "text/html")))

    def test_no_parser_for_images(self):
        image = _build_http_response("", "image/png")

        with self.assertRaisesRegex(BaseFrameworkException, "There is no parser"):
            self.dpc.get_document_parser_for(image)

        self.assertEqual(self.dpc.get_tags_by_filter(image, None), [])

    def test_parser_not_cached(self):
        first = self.dpc.get_document_parser_for(self.http_resp, cache=False)
        second = self.dpc.get_document_parser_for(self.http_resp, cache=False)

        self.assertIsNot(first, second)
        self.assertEqual(len(self.dpc._cache), 0)

    def test_tags_not_cached(self):
        first = self.dpc.get_tags_by_filter(self.http_resp, ("a",), cache=False)
        second = self.dpc.get_tags_by_filter(self.http_resp, ("a",), cache=False)

        self.assertEqual(first, second)
        self.assertIsNot(first, second)

    def test_tags_without_filter(self):
        tags = self.dpc.get_tags_by_filter(self.http_resp, None)

        self.assertIn("a", [tag.name for tag in tags])

    def test_tags_not_in_body(self):
        self.assertEqual(self.dpc.get_tags_by_filter(self.http_resp, ("form",)), [])

    def test_tags_blacklisted(self):
        hash_string = get_body_unique_id(self.http_resp, prepend="('a',)False")
        self.dpc.add_to_blacklist(hash_string)

        self.assertEqual(self.dpc.get_tags_by_filter(self.http_resp, ("a",)), [])

    def test_clear_releases_cached_parsers_and_tags(self):
        self.dpc.get_document_parser_for(self.http_resp)
        self.dpc.get_tags_by_filter(self.http_resp, ("a",))

        self.dpc.clear()

        self.assertEqual(len(self.dpc._cache), 0)
        self.assertEqual(len(self.dpc._can_parse_cache), 0)

    def test_clear_releases_parser_state(self):
        hash_string = get_response_unique_id(self.http_resp)
        self.dpc._parser_finished_events[hash_string] = threading.Event()
        self.dpc.add_to_blacklist(hash_string)

        self.dpc.clear()

        self.assertEqual(self.dpc._parser_finished_events, {})
        self.assertEqual(len(self.dpc._parser_blacklist), 0)


class TestParserCacheCleanup(unittest.TestCase):
    def test_cleanup_pool_clears_the_shared_cache(self):
        http_resp = _build_http_response(HTML_OK % "", "text/html")
        parser_cache.dpc.get_document_parser_for(http_resp)

        parser_cache.cleanup_pool()

        self.assertEqual(len(parser_cache.dpc._cache), 0)


class TestWorkerFailureParsers(unittest.TestCase):
    """
    These parsers break the communication with the worker processes, here
    they run in this process to verify what they do on their own.
    """

    def build_parser(self, parser_class):
        response = _build_http_response(
            f"<html>{parser_class.MARKER}!</html>", "text/html"
        )
        return parser_class(response)

    def test_unloadable_parser_is_reduced_to_a_failing_loader(self):
        parser = self.build_parser(UnloadableParser)

        self.assertIsNone(parser.parse())

        loader, loader_args = parser.__reduce__()
        with self.assertRaisesRegex(ValueError, "can not be loaded"):
            loader(*loader_args)

    def test_bad_tags_parser_yields_tags_without_content(self):
        parser = self.build_parser(BadTagsParser)

        self.assertIsNone(parser.parse())

        tags = list(parser.get_tags_by_filter(("html",)))
        self.assertEqual([tag.to_dict() for tag in tags], [{}])


def raise_on_load():
    raise ValueError("This parser can not be loaded in the main process")


class UnloadableParser(_MarkerParser):
    MARKER = "UnloadableParser"

    def parse(self):
        return None

    def __reduce__(self):
        return raise_on_load, ()


class BadTagsParser(_MarkerParser):
    MARKER = "BadTagsParser"

    def parse(self):
        return None

    def get_tags_by_filter(self, tags, yield_text=False):
        yield NotATag()


class NotATag:
    def to_dict(self):
        return {}
