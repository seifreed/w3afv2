"""Tests for bounded request metrics."""

import unittest

from w3af.core.data.dc.headers import Headers
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.url.http_response import HTTPResponse
from w3af.core.data.url.request_metrics import RequestMetrics


class TestRequestMetrics(unittest.TestCase):
    def test_request_count_can_be_reset_without_clearing_rtt(self):
        metrics = RequestMetrics()
        url = URL("http://w3af.com")
        response = HTTPResponse(200, "", Headers(), url, url, time=1.5)

        metrics.increment_requests()
        metrics.track_rtt(response, "did")
        metrics.reset_total_requests()

        self.assertEqual(metrics.get_total_requests(), 0)
        self.assertEqual(metrics.get_rtt("did"), 1.5)

    def test_rtt_is_accumulated_for_a_debugging_id(self):
        metrics = RequestMetrics()
        url = URL("http://w3af.com")
        response = HTTPResponse(200, "", Headers(), url, url, time=1.5)

        metrics.track_rtt(response, "did")
        metrics.track_rtt(response, "did")

        self.assertEqual(metrics.get_rtt("did"), 3.0)

    def test_response_without_wait_time_is_ignored(self):
        metrics = RequestMetrics()

        metrics.track_rtt(object(), "did")

        self.assertIsNone(metrics.get_rtt("did"))

    def test_none_debugging_id_has_no_rtt(self):
        self.assertIsNone(RequestMetrics().get_rtt(None))

    def test_rtt_cache_is_bounded(self):
        metrics = RequestMetrics()
        url = URL("http://w3af.com")
        response = HTTPResponse(200, "", Headers(), url, url, time=1.5)

        for debugging_id in range(129):
            metrics.track_rtt(response, debugging_id)

        self.assertIsNone(metrics.get_rtt(0))
        self.assertEqual(metrics.get_rtt(128), 1.5)

    def test_clear_rtt(self):
        metrics = RequestMetrics()
        url = URL("http://w3af.com")
        response = HTTPResponse(200, "", Headers(), url, url, time=1.5)
        metrics.track_rtt(response, "did")

        metrics.clear_rtt()

        self.assertIsNone(metrics.get_rtt("did"))
