"""
test_get_average_rtt.py

Copyright 2018 Andres Riancho

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
from itertools import repeat
from multiprocessing.dummy import Pool as ThreadPool

import pytest

from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.request.fuzzable_request import FuzzableRequest
from w3af.core.data.url.exceptions import HTTPRequestException
from w3af.core.data.url.extended_urllib import ExtendedUrllib
from w3af.core.data.url.get_average_rtt import GetAverageRTTForMutant
from w3af.core.data.url.tests.helpers.route_server import Response, RouteServer

# Generous upper bound: the machine running the tests might be under load
SLOW_MACHINE_MARGIN = 3.0


class DelayedResponder:
    """
    Answer each request after sleeping for the next delay in the list, the
    last delay is reused once the list is exhausted.
    """

    def __init__(self, delays):
        self.delays = list(delays)
        self.lock = threading.Lock()

    def __call__(self, request):
        with self.lock:
            delay = self.delays.pop(0) if len(self.delays) > 1 else self.delays[0]

        time.sleep(delay)
        return Response(200, "Yup")


class GatedResponder:
    """
    Hold the first request until `release` is set and then close the
    connection without answering it. Every other request is answered
    immediately.
    """

    def __init__(self):
        self.first_received = threading.Event()
        self.release = threading.Event()
        self.lock = threading.Lock()
        self.calls = 0

    def __call__(self, request):
        with self.lock:
            self.calls += 1
            is_first = self.calls == 1

        if is_first:
            self.first_received.set()
            self.release.wait(60)
            return Response(drop=True)

        return Response(200, "Yup")


@pytest.mark.smoke
class TestGetAverageRTT(unittest.TestCase):

    def setUp(self):
        self.uri_opener = ExtendedUrllib()
        self.addCleanup(self.uri_opener.end)
        self.addCleanup(self.uri_opener.settings.set_default_values)

    def serve(self, responder):
        server = RouteServer.serve_for(self, {"/": responder})
        return FuzzableRequest(URL(server.url())), server

    def test_get_average_rtt_for_mutant_all_equal(self):
        fuzzable_request, _ = self.serve(DelayedResponder([0.5]))

        average_rtt = self.uri_opener.get_average_rtt_for_mutant(fuzzable_request)

        self.assertGreaterEqual(average_rtt, 0.5)
        self.assertLess(average_rtt, 0.5 + SLOW_MACHINE_MARGIN)

    def test_get_average_rtt_for_mutant_one_off(self):
        fuzzable_request, _ = self.serve(DelayedResponder([0.3, 0.2, 2.0]))

        average_rtt = self.uri_opener.get_average_rtt_for_mutant(fuzzable_request)

        self.assertGreaterEqual(average_rtt, 2.5 / 3)
        self.assertLess(average_rtt, 2.5 / 3 + SLOW_MACHINE_MARGIN)

    def test_count_must_be_at_least_three(self):
        fuzzable_request, server = self.serve(DelayedResponder([0]))

        self.assertRaises(
            ValueError,
            self.uri_opener.get_average_rtt_for_mutant,
            fuzzable_request,
            count=2,
        )
        self.assertEqual(server.requests, [])

    def test_cached_rtt_is_reused(self):
        fuzzable_request, server = self.serve(DelayedResponder([0.1]))

        first = self.uri_opener.get_average_rtt_for_mutant(fuzzable_request)
        second = self.uri_opener.get_average_rtt_for_mutant(fuzzable_request)

        self.assertEqual(first, second)
        self.assertEqual(len(server.requests), 3)

    def test_expired_cache_entry_is_measured_again(self):
        fuzzable_request, server = self.serve(DelayedResponder([0.1]))
        rtt_getter = GetAverageRTTForMutant(self.uri_opener, cache_ttl=0)

        rtt_getter.get_average_rtt_for_mutant(fuzzable_request)
        time.sleep(0.05)
        rtt_getter.get_average_rtt_for_mutant(fuzzable_request)

        self.assertEqual(len(server.requests), 6)

    def test_get_average_rtt_for_mutant_with_threads(self):
        fuzzable_request, server = self.serve(DelayedResponder([0.5]))

        pool = ThreadPool(25)
        self.addCleanup(pool.terminate)

        iterations = 50

        results = pool.map(
            self.uri_opener.get_average_rtt_for_mutant,
            repeat(fuzzable_request, iterations),
        )

        self.assertEqual(len(results), iterations)
        self.assertEqual(set(results), {results[0]})
        self.assertGreaterEqual(results[0], 0.5)

        # Only one thread sent requests, the rest waited for it
        self.assertEqual(len(server.requests), 3)

    def _start_first_measurement(self, rtt_getter, fuzzable_request, responder):
        errors = []

        def measure():
            try:
                rtt_getter.get_average_rtt_for_mutant(fuzzable_request)
            except HTTPRequestException as hre:
                errors.append(hre)

        first = threading.Thread(target=measure, daemon=True)
        first.start()
        self.assertTrue(responder.first_received.wait(30))
        return first, errors

    def test_measure_again_when_waiting_times_out(self):
        responder = GatedResponder()
        fuzzable_request, server = self.serve(responder)
        self.uri_opener.settings.set_max_http_retries(0)

        rtt_getter = GetAverageRTTForMutant(self.uri_opener, timeout=0.1)
        first, errors = self._start_first_measurement(
            rtt_getter, fuzzable_request, responder
        )

        # The first thread is still waiting for its response, this one gives
        # up waiting and measures the RTT itself
        average_rtt = rtt_getter.get_average_rtt_for_mutant(fuzzable_request)

        responder.release.set()
        first.join(30)

        self.assertGreater(average_rtt, 0)
        self.assertEqual(len(errors), 1)
        self.assertEqual(len(server.requests), 4)

    def test_measure_again_when_other_thread_failed(self):
        responder = GatedResponder()
        fuzzable_request, server = self.serve(responder)
        self.uri_opener.settings.set_max_http_retries(0)

        rtt_getter = GetAverageRTTForMutant(self.uri_opener)
        first, errors = self._start_first_measurement(
            rtt_getter, fuzzable_request, responder
        )

        results = []
        second = threading.Thread(
            target=lambda: results.append(
                rtt_getter.get_average_rtt_for_mutant(fuzzable_request)
            ),
            daemon=True,
        )
        second.start()

        # Give the second thread time to start waiting for the first one
        time.sleep(2)
        responder.release.set()

        first.join(30)
        second.join(30)

        # The first thread failed without caching anything, so the second
        # one measured the RTT itself after waiting for the first
        self.assertEqual(len(errors), 1)
        self.assertEqual(len(results), 1)
        self.assertGreater(results[0], 0)
        self.assertEqual(len(server.requests), 4)
