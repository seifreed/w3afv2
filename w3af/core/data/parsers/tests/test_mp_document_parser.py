"""
test_mp_document_parser.py

Copyright 2015 Andres Riancho

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

import contextlib
import io
import multiprocessing
import os
import resource
import signal
import time
import unittest
from concurrent.futures import TimeoutError
from queue import Queue

import w3af.core.data.parsers.mp_document_parser as mp_module
from w3af import ROOT_PATH
from w3af.core.data.dc.headers import Headers
from w3af.core.data.parsers.doc.html import HTMLParser
from w3af.core.data.parsers.doc.sgml import Tag
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.parsers.document_parser import DocumentParser
from w3af.core.data.parsers.ipc.serialization import (
    load_object_from_temp_file,
    load_tags_from_temp_file,
    remove_file_if_exists,
    write_http_response_to_temp_file,
)
from w3af.core.data.parsers.mp_document_parser import (
    DEFAULT_MEMORY_LIMIT,
    DocumentParsingError,
    MultiProcessingDocumentParser,
    ParserMemoryLimitError,
    apply_with_return_error,
    configure_multiprocessing,
    get_memory_limit,
    init_worker,
    limit_memory_usage,
    process_document_parser,
    process_get_tags_by_filter,
)
from w3af.core.data.parsers.tests.test_document_parser import _build_http_response
from w3af.core.data.url.http_response import HTTPResponse
from w3af.core.exceptions import BaseFrameworkException, ScanMustStopException

HTML_OK = "<html><a href='/abc'>foo-</a></html>%s"
HTML_DELAYED = "<html>DelayedParser!</html>%s"
MEMORY_LIMIT = 128 * 1024 * 1024
FIXTURE_8748 = os.path.join(
    ROOT_PATH, "core", "data", "parsers", "doc", "tests", "data", "dictproxy-8748.htm"
)


class TestMPDocumentParser(unittest.TestCase):

    def setUp(self):
        self.url = URL("http://w3af.com")
        self.headers = Headers([("content-type", "text/html")])
        self.mpdoc = MultiProcessingDocumentParser()

    def tearDown(self):
        self.mpdoc.stop_workers()

    def use_parsers(self, *parsers, **kwargs):
        self.mpdoc.stop_workers()
        self.mpdoc = MultiProcessingDocumentParser(
            parsers=(*parsers, HTMLParser), **kwargs
        )

    def test_max_workers_is_a_positive_integer(self):
        self.assertIsInstance(MultiProcessingDocumentParser.MAX_WORKERS, int)
        self.assertGreaterEqual(MultiProcessingDocumentParser.MAX_WORKERS, 1)
        self.assertEqual(
            self.mpdoc.max_workers, MultiProcessingDocumentParser.MAX_WORKERS
        )

    def test_basic(self):
        resp = HTTPResponse(
            200, '<a href="/abc">hello</a>', self.headers, self.url, self.url
        )

        parser = self.mpdoc.get_document_parser_for(resp)

        parsed_refs, _ = parser.get_references()
        self.assertEqual([URL("http://w3af.com/abc")], parsed_refs)

    def test_start_workers_reuses_the_pool(self):
        pool = self.mpdoc.start_workers()
        self.assertIs(self.mpdoc.start_workers(), pool)

    def test_no_parser_for_images(self):
        url = URL("http://w3af.com/foo.jpg")
        headers = Headers([("content-type", "image/jpeg")])
        resp = HTTPResponse(200, "", headers, url, url)

        with self.assertRaises(DocumentParsingError) as context:
            self.mpdoc.get_document_parser_for(resp)

        self.assertEqual(str(context.exception), "There is no parser for images.")
        self.assertIsInstance(context.exception.__cause__, BaseFrameworkException)

    def test_parser_timeout(self):
        """
        Test to verify fix for https://github.com/andresriancho/w3af/issues/6723
        "w3af running long time more than 24h"
        """
        self.use_parsers(DelayedParser, parser_timeout=2, max_workers=1)

        http_resp = _build_http_response(HTML_DELAYED % "", "text/html")

        with self.assertRaises(TimeoutError) as context:
            self.mpdoc.get_document_parser_for(http_resp)

        self._assert_timeout_message(context.exception, http_resp)

        #
        # After the worker is killed the pool must create a new process to
        # handle our tasks: https://github.com/andresriancho/w3af/issues/9713
        #
        http_resp = _build_http_response(HTML_OK % "", "text/html")

        doc_parser = self.mpdoc.get_document_parser_for(http_resp)
        self.assertIsInstance(doc_parser.get_parser(), HTMLParser)

    def test_many_parsers_timing_out(self):
        """
        Received more reports of parsers timing out, and after that
        w3af showing always "The parser took more than X seconds to complete
        parsing of" for all calls to the parser.

        Want to test how well the the parser recovers from many timeouts.
        """
        self.use_parsers(DelayedParser, parser_timeout=2, max_workers=2)

        for i in range(4):
            http_resp = _build_http_response(HTML_DELAYED % i, "text/html")

            with self.assertRaises(TimeoutError) as context:
                self.mpdoc.get_document_parser_for(http_resp)

            self._assert_timeout_message(context.exception, http_resp)

            http_resp = _build_http_response(HTML_OK % i, "text/html")
            parser = self.mpdoc.get_document_parser_for(http_resp)
            self.assertIsInstance(parser.get_parser(), HTMLParser)

    def test_parser_memory_usage_exceeded(self):
        """
        This makes sure that we stop parsing a document that exceeds our memory
        usage limits.
        """
        self.use_parsers(UseMemoryParser, memory_limit=MEMORY_LIMIT, max_workers=1)

        http_resp = _build_http_response("<html>UseMemoryParser!</html>", "text/html")

        with self.assertRaises(ParserMemoryLimitError) as context:
            self.mpdoc.get_document_parser_for(http_resp)

        self.assertIn("OOM issues", str(context.exception))
        self.assertIn(str(MEMORY_LIMIT), str(context.exception))

        #
        # After we stop because of a memory issue the pool continues handling
        # tasks as expected
        #
        http_resp = _build_http_response(HTML_OK % "", "text/html")

        doc_parser = self.mpdoc.get_document_parser_for(http_resp)
        self.assertIsInstance(doc_parser.get_parser(), HTMLParser)

    def test_parser_process_dies(self):
        self.use_parsers(DyingParser, max_workers=1)

        http_resp = _build_http_response("<html>DyingParser!</html>", "text/html")

        with self.assertRaises(TimeoutError) as context:
            self.mpdoc.get_document_parser_for(http_resp)

        self.assertIn("died unexpectedly", str(context.exception))
        self.assertEqual(self.mpdoc.get_tags_by_filter(http_resp, ("html",)), [])

    def test_stopped_pool_stops_the_scan(self):
        pool = self.mpdoc.start_workers()
        pool.stop()
        pool.join()

        http_resp = _build_http_response(HTML_OK % "", "text/html")

        self.assertRaises(
            ScanMustStopException, self.mpdoc.get_document_parser_for, http_resp
        )
        self.assertRaises(
            ScanMustStopException, self.mpdoc.get_tags_by_filter, http_resp, ("a",)
        )

    def _assert_timeout_message(self, toe, http_resp):
        msg = (
            "[timeout] The parser took more than %s seconds to "
            'complete parsing of "%s", killed it!'
        )

        error = msg % (self.mpdoc.parser_timeout, http_resp.get_url())

        self.assertEqual(str(toe), error)

    def test_daemon_child(self):
        """
        Reproduces:

            A "AssertionError" exception was found while running
            crawl.web_spider on "Method: GET | http://domain:8000/". The
            exception was: "daemonic processes are not allowed to have children"
            at process.py:start():124. The scan will continue but some
            vulnerabilities might not be identified.
        """
        queue = multiprocessing.Queue()

        p = multiprocessing.Process(target=daemon_child, args=(queue,))
        p.daemon = True
        p.start()
        p.join()

        self.assertTrue(queue.get(timeout=60))

    def test_non_daemon_child_ok(self):
        """
        Making sure that the previous failure is due to "p.daemon = True"
        """
        queue = multiprocessing.Queue()

        p = multiprocessing.Process(target=daemon_child, args=(queue,))
        p.start()
        p.join()

        self.assertTrue(queue.get(timeout=60))

    def test_dictproxy_8748(self):
        """
        MaybeEncodingError serializing a dictproxy
        https://github.com/andresriancho/w3af/issues/8748
        """
        with open(FIXTURE_8748, encoding="latin-1") as html_file:
            body = html_file.read()

        url = URL("http://www.ensinosuperior.org.br/asesi.htm")
        resp = HTTPResponse(200, body, self.headers, url, url)

        parser = self.mpdoc.get_document_parser_for(resp)
        self.assertIsInstance(parser.get_parser(), HTMLParser)

    def test_get_tags_by_filter(self):
        body = '<html><a href="/abc">foo</a><b>bar</b></html>'
        resp = _build_http_response(body, "text/html")

        tags = self.mpdoc.get_tags_by_filter(resp, ("a", "b"), yield_text=True)

        self.assertEqual([Tag("a", {"href": "/abc"}, "foo"), Tag("b", {}, "bar")], tags)

    def test_get_tags_by_filter_empty_tag(self):
        body = '<html><script src="foo.js"></script></html>'
        resp = _build_http_response(body, "text/html")

        tags = self.mpdoc.get_tags_by_filter(resp, ("script",), yield_text=True)

        # Note that lxml returns None for this tag text:
        self.assertEqual([Tag("script", {"src": "foo.js"}, None)], tags)

    def test_get_tags_by_filter_parser_without_tags(self):
        self.use_parsers(TaglessParser, max_workers=1)

        resp = _build_http_response("<html>TaglessParser!</html>", "text/html")

        self.assertEqual(self.mpdoc.get_tags_by_filter(resp, ("html",)), [])

    def test_get_tags_by_filter_timeout(self):
        self.use_parsers(DelayedParser, parser_timeout=2, max_workers=1)

        resp = _build_http_response(HTML_DELAYED % "", "text/html")

        self.assertEqual(self.mpdoc.get_tags_by_filter(resp, ("html",)), [])

    def test_get_tags_by_filter_memory_limit(self):
        self.use_parsers(UseMemoryParser, memory_limit=MEMORY_LIMIT, max_workers=1)

        resp = _build_http_response("<html>UseMemoryParser!</html>", "text/html")

        self.assertEqual(self.mpdoc.get_tags_by_filter(resp, ("html",)), [])

    def test_get_tags_by_filter_parser_error(self):
        self.use_parsers(FailingParser, max_workers=1)

        resp = _build_http_response("<html>FailingParser!</html>", "text/html")

        self.assertEqual(self.mpdoc.get_tags_by_filter(resp, ("html",)), [])

    def test_configured_worker_initializer_receives_log_queue(self):
        previous = (mp_module._LOG_QUEUE_PROVIDER, mp_module._WORKER_INITIALIZER)
        self.addCleanup(configure_multiprocessing, *previous)

        queue = multiprocessing.Queue()
        configure_multiprocessing(lambda: queue, announce_worker)

        response = _build_http_response(HTML_OK % "", "text/html")
        self.mpdoc.get_tags_by_filter(response, ("a",))

        self.assertEqual(queue.get(timeout=60), "worker ready")


class TestWorkerFunctions(unittest.TestCase):
    """
    The functions below run inside the pool workers, call them here so their
    behaviour is verified in-process.
    """

    def setUp(self):
        self.html = _build_http_response(HTML_OK % "", "text/html")
        self.filename = write_http_response_to_temp_file(self.html)
        self.addCleanup(remove_file_if_exists, self.filename)

    def test_apply_with_return_error(self):
        self.assertEqual(apply_with_return_error((max, 3, 7)), 7)

        error = apply_with_return_error((int, "not a number"))
        self.assertIsInstance(error.exc_value, ValueError)

    def test_process_document_parser(self):
        result = process_document_parser(self.filename, True, DocumentParser.PARSERS)
        self.addCleanup(remove_file_if_exists, result)

        document_parser = load_object_from_temp_file(result)
        self.assertIsInstance(document_parser.get_parser(), HTMLParser)

    def test_process_document_parser_error(self):
        url = URL("http://w3af.com/foo.jpg")
        headers = Headers([("content-type", "image/png")])
        image = HTTPResponse(200, "", headers, url, url)

        for debug in (True, False):
            filename = write_http_response_to_temp_file(image)
            self.addCleanup(remove_file_if_exists, filename)

            self.assertRaises(
                BaseFrameworkException,
                process_document_parser,
                filename,
                debug,
                DocumentParser.PARSERS,
            )

    def test_process_get_tags_by_filter(self):
        result = process_get_tags_by_filter(
            self.filename, ("a",), True, False, DocumentParser.PARSERS
        )
        self.addCleanup(remove_file_if_exists, result)

        self.assertEqual(
            load_tags_from_temp_file(result), [Tag("a", {"href": "/abc"}, "foo-")]
        )

    def test_process_get_tags_by_filter_parser_without_tags(self):
        response = _build_http_response("<html>TaglessParser!</html>", "text/html")
        filename = write_http_response_to_temp_file(response)
        self.addCleanup(remove_file_if_exists, filename)

        result = process_get_tags_by_filter(
            filename, ("a",), False, False, (TaglessParser,)
        )
        self.addCleanup(remove_file_if_exists, result)

        self.assertEqual(load_tags_from_temp_file(result), [])


class TestWorkerSetup(unittest.TestCase):

    def setUp(self):
        sigint = signal.getsignal(signal.SIGINT)
        self.addCleanup(signal.signal, signal.SIGINT, sigint)

        limits = resource.getrlimit(mp_module.RLIMIT_AS)
        self.addCleanup(resource.setrlimit, mp_module.RLIMIT_AS, limits)

    def test_init_worker(self):
        received = []

        init_worker(received.append, "log-queue", 2**40)

        self.assertEqual(received, ["log-queue"])
        self.assertEqual(signal.getsignal(signal.SIGINT), signal.SIG_IGN)

    def test_init_worker_without_initializer(self):
        init_worker(None, None, 2**40)

        self.assertEqual(signal.getsignal(signal.SIGINT), signal.SIG_IGN)

    def test_limit_memory_usage(self):
        hard = resource.getrlimit(mp_module.RLIMIT_AS)[1]

        limit_memory_usage(2**40)

        soft, new_hard = resource.getrlimit(mp_module.RLIMIT_AS)
        self.assertGreater(soft, 2**40)
        self.assertEqual(new_hard, hard)

    def test_limit_memory_usage_unsupported_platform(self):
        limits = resource.getrlimit(mp_module.RLIMIT_AS)
        output = io.StringIO()

        with contextlib.redirect_stdout(output):
            limit_memory_usage(2**40, rlimit=None)

        self.assertIn("only supported in Linux", output.getvalue())
        self.assertEqual(resource.getrlimit(mp_module.RLIMIT_AS), limits)


class TestMemoryLimitConfiguration(unittest.TestCase):

    def setUp(self):
        self.addCleanup(self.restore, dict(os.environ))
        os.environ.pop("PARSER_MEMORY_LIMIT", None)

    @staticmethod
    def restore(environment):
        os.environ.clear()
        os.environ.update(environment)

    def test_default(self):
        self.assertEqual(get_memory_limit(), DEFAULT_MEMORY_LIMIT)

    def test_from_environment(self):
        os.environ["PARSER_MEMORY_LIMIT"] = "1234"
        output = io.StringIO()

        with contextlib.redirect_stdout(output):
            self.assertEqual(get_memory_limit(), 1234)

        self.assertIn("1234", output.getvalue())

    def test_invalid_environment_value_is_ignored(self):
        os.environ["PARSER_MEMORY_LIMIT"] = "lots"
        self.assertEqual(get_memory_limit(), DEFAULT_MEMORY_LIMIT)


class TestCleanupPool(unittest.TestCase):
    def test_parser_can_stop_its_owned_workers(self):
        parser = MultiProcessingDocumentParser()
        parser.start_workers()

        parser.stop_workers()

        self.assertIsNone(parser._pool)


class TestMarkerParsers(unittest.TestCase):
    """
    The marker parsers misbehave inside of the worker processes, these tests
    run them in this process with harmless settings.
    """

    def build_parser(self, parser_class):
        response = _build_http_response(
            f"<html>{parser_class.MARKER}!</html>", "text/html"
        )
        return parser_class(response)

    def test_delayed_parser_waits_the_configured_time(self):
        class NoDelayParser(DelayedParser):
            DELAY_SECONDS = 0

        self.assertIsNone(self.build_parser(NoDelayParser).parse())

    def test_memory_parser_allocates_the_configured_memory(self):
        class SmallMemoryParser(UseMemoryParser):
            MEMORY_BYTES = 16

        parser = self.build_parser(SmallMemoryParser)
        parser.parse()

        self.assertEqual(len(parser.memory), 16)

    def test_dying_parser_exits_the_process_with_an_error_code(self):
        exit_codes = []

        class SurvivingParser(DyingParser):
            EXIT = staticmethod(exit_codes.append)

        self.build_parser(SurvivingParser).parse()

        self.assertEqual(exit_codes, [1])

    def test_marker_parsers_can_be_cleared(self):
        self.assertTrue(self.build_parser(DelayedParser).clear())

    def test_announce_worker_reports_to_the_log_queue(self):
        log_queue = Queue()

        announce_worker(log_queue)

        self.assertEqual(log_queue.get_nowait(), "worker ready")

    def test_failing_parser_raises(self):
        with self.assertRaisesRegex(ValueError, "Broken document"):
            self.build_parser(FailingParser).parse()


def daemon_child(queue):
    dpc = MultiProcessingDocumentParser()

    try:
        dpc.start_workers()
        queue.put(True)
    finally:
        dpc.stop_workers()


def announce_worker(log_queue):
    log_queue.put("worker ready")


class _MarkerParser:
    MARKER = ""

    def __init__(self, http_response):
        self.http_response = http_response

    @classmethod
    def can_parse(cls, http_response):
        return cls.MARKER in http_response.get_body()

    def clear(self):
        return True


class DelayedParser(_MarkerParser):
    MARKER = "DelayedParser"
    DELAY_SECONDS = 60

    def parse(self):
        time.sleep(self.DELAY_SECONDS)


class UseMemoryParser(_MarkerParser):
    MARKER = "UseMemoryParser"
    MEMORY_BYTES = 2 * 1024 * 1024 * 1024

    def parse(self):
        self.memory = bytearray(self.MEMORY_BYTES)


class DyingParser(_MarkerParser):
    MARKER = "DyingParser"

    EXIT = staticmethod(os._exit)

    def parse(self):
        self.EXIT(1)


class FailingParser(_MarkerParser):
    MARKER = "FailingParser"

    def parse(self):
        raise ValueError("Broken document")


class TaglessParser(_MarkerParser):
    MARKER = "TaglessParser"

    def parse(self):
        return None
