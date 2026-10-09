"""
test_decorators.py

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
import time
import unittest

import w3af.core.controllers.output_manager as om
from w3af.core.controllers.core_helpers.not_found.decorators import (
    LRUCache404,
    PreventMultipleThreads,
)
from w3af.core.controllers.tests.recording_output import start_recording_output
from w3af.core.data.dc.headers import Headers
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.url.http_response import HTTPResponse
from w3af.core.data.url.not_found_response import FourOhFourResponse

RELEASE_TIMEOUT = 10


def build_response(url, body="Page body", code=200):
    url = URL(url)
    headers = Headers([("Content-Type", "text/html")])
    return HTTPResponse(code, body, headers, url, url)


def record_output(test_case):
    recorder = start_recording_output()
    test_case.addCleanup(om.manager.get_output_plugin_inst().remove, recorder)
    return recorder


class StatsEveryCallLRUCache404(LRUCache404):
    STATS_EVERY = 1


class CountingDetector:
    """
    Runs a real (and trivial) 404 detection algorithm wrapped by
    LRUCache404, counting how many times the algorithm was run.
    """

    def __init__(self):
        self.calls = 0
        self._cached_is_404 = StatsEveryCallLRUCache404(self._is_404)

    def _is_404(self, http_response, query):
        self.calls += 1
        return http_response.get_code() == 404

    def query(self, http_response):
        return self._cached_is_404(
            http_response, FourOhFourResponse.from_http_response(http_response)
        )


class TestLRUCache404(unittest.TestCase):
    def test_runs_the_function_for_unknown_responses(self):
        detector = CountingDetector()

        self.assertTrue(detector.query(build_response("http://w3af.org/a", code=404)))
        self.assertFalse(detector.query(build_response("http://w3af.org/b", "other")))
        self.assertEqual(detector.calls, 2)

    def test_url_cache_hit(self):
        detector = CountingDetector()
        response = build_response("http://w3af.org/dir/a.html", code=404)
        recorder = record_output(self)

        self.assertTrue(detector.query(response))
        self.assertTrue(detector.query(response))

        self.assertEqual(detector.calls, 1)
        self.assertTrue(
            any(
                "is a 404 [URL 404 cache]" in message
                for message in recorder.messages_of("debug")
            )
        )

    def test_body_cache_hit(self):
        detector = CountingDetector()
        recorder = record_output(self)

        first = build_response("http://w3af.org/dir/a.html", "Same body")
        second = build_response("http://w3af.org/dir/b.html", "Same body")

        self.assertFalse(detector.query(first))
        self.assertFalse(detector.query(second))

        self.assertEqual(detector.calls, 1)
        self.assertTrue(
            any(
                "is NOT a 404 [body 404 cache]" in message
                for message in recorder.messages_of("debug")
            )
        )

    def test_logs_cache_hit_rate(self):
        detector = CountingDetector()
        recorder = record_output(self)
        response = build_response("http://w3af.org/c", code=404)

        detector.query(response)
        detector.query(response)
        detector.query(response)

        self.assertIn(
            "The 404 cache has a 33.33 % hit rate", recorder.messages_of("debug")
        )

    def test_each_instance_has_its_own_cache(self):
        response = build_response("http://w3af.org/d", code=404)
        first = CountingDetector()
        second = CountingDetector()

        first.query(response)
        second.query(response)

        self.assertEqual((first.calls, second.calls), (1, 1))

    def test_get_url_cache_key_depends_on_the_uri(self):
        key_a = LRUCache404.get_url_cache_key(build_response("http://w3af.org/a"))
        key_b = LRUCache404.get_url_cache_key(build_response("http://w3af.org/b"))

        self.assertNotEqual(key_a, key_b)


class QuickTimeoutPreventMultipleThreads(PreventMultipleThreads):
    TIMEOUT = 0.2


class BlockingDetector:
    """
    The 404 detection blocks until the test releases it, which allows the
    tests to send concurrent calls for the same normalized path.
    """

    def __init__(self, wrapper_class=PreventMultipleThreads):
        self.calls = 0
        self.started = threading.Event()
        self.release = threading.Event()
        self.is_404 = wrapper_class(self._is_404)

    def _is_404(self, http_response):
        self.calls += 1
        self.started.set()
        self.release.wait(RELEASE_TIMEOUT)
        return self.calls == 1


def call_in_thread(function, http_response, results):
    thread = threading.Thread(target=lambda: results.append(function(http_response)))
    thread.start()
    return thread


class TestPreventMultipleThreads(unittest.TestCase):
    def test_single_call_runs_the_function(self):
        detector = BlockingDetector()
        detector.release.set()

        self.assertTrue(detector.is_404(build_response("http://w3af.org/x/a.html")))
        self.assertEqual(detector.calls, 1)

    def test_second_call_for_same_path_waits_for_the_first(self):
        detector = BlockingDetector()
        first_results = []
        second_results = []

        first = call_in_thread(
            detector.is_404, build_response("http://w3af.org/x/a.html"), first_results
        )
        detector.started.wait(RELEASE_TIMEOUT)

        second = call_in_thread(
            detector.is_404, build_response("http://w3af.org/x/b.html"), second_results
        )
        time.sleep(0.3)
        self.assertEqual(detector.calls, 1)

        detector.release.set()
        first.join()
        second.join()

        self.assertEqual(first_results, [True])
        self.assertEqual(second_results, [False])
        self.assertEqual(detector.calls, 2)

    def test_waiting_call_times_out(self):
        detector = BlockingDetector(QuickTimeoutPreventMultipleThreads)
        recorder = record_output(self)
        first_results = []

        first = call_in_thread(
            detector.is_404, build_response("http://w3af.org/y/a.html"), first_results
        )
        detector.started.wait(RELEASE_TIMEOUT)

        try:
            result = detector.is_404(build_response("http://w3af.org/y/b.html"))
        finally:
            detector.release.set()
            first.join()

        self.assertTrue(result)
        self.assertEqual(detector.calls, 1)
        self.assertTrue(
            any(
                "is_404() took more than 0.2 seconds" in message
                for message in recorder.messages_of("error")
            )
        )
