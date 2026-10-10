"""Tests for response history metrics and stop detection."""

import unittest

from w3af.core.data.url.response_history import ResponseHistory


class TestResponseHistory(unittest.TestCase):
    def setUp(self):
        self.history = ResponseHistory()

    def test_reset_clears_failures(self):
        self.history.record_failure("failed", "example.com", 1.0)

        self.assertEqual(self.history.get_error_rate(), 1)

        self.history.reset()

        self.assertEqual(self.history.get_error_rate(), 0)

    def test_get_average_rtt_filters_by_host(self):
        self.history.record_success("example.com", 1.0)
        self.history.record_success("other.example", 3.0)
        self.history.record_failure("failed", "example.com", 5.0)

        self.assertEqual(self.history.get_average_rtt(3), (3.0, 3))
        self.assertEqual(self.history.get_average_rtt(3, "example.com"), (3.0, 2))

    def test_should_stop_scan_checks_server_reachability(self):
        for _ in range(10):
            self.history.record_failure("failed", "example.com", 1.0)

        reachable_checks = []

        def server_is_reachable():
            reachable_checks.append(True)
            return False

        self.assertTrue(self.history.should_stop_scan(server_is_reachable))
        self.assertEqual(reachable_checks, [True])

        self.history.reset()
        for _ in range(10):
            self.history.record_failure("failed", "example.com", 1.0)

        self.assertFalse(self.history.should_stop_scan(lambda: True))

    def test_should_stop_scan_ignores_non_consecutive_failures(self):
        self.history.record_failure("failed", "example.com", 1.0)
        for _ in range(9):
            self.history.record_success("example.com", 1.0)

        self.assertFalse(self.history.should_stop_scan(lambda: False))

    def test_get_recent_messages_returns_latest_entries(self):
        self.history.record_failure("first", "example.com", 1.0)
        self.history.record_failure("last", "example.com", 1.0)

        self.assertEqual(self.history.get_recent_messages(2), ["first", "last"])
