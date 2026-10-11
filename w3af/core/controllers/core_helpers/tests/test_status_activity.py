"""Tests for scan status activity state."""

import unittest

from w3af.core.controllers.core_helpers.status_activity import StatusActivity


class TestStatusActivity(unittest.TestCase):
    def test_tracks_current_and_latest_activity(self):
        activity = StatusActivity()

        self.assertIsNone(activity.get_running_plugin("crawl"))
        self.assertIsNone(activity.get_current_fuzzable_request("crawl"))
        self.assertEqual(activity.latest_running_plugin(), (None, None))

        activity.set_running_plugin("crawl", "web_spider")
        activity.set_current_fuzzable_request("crawl", "request")

        self.assertEqual(activity.get_running_plugin("crawl"), "web_spider")
        self.assertEqual(activity.get_current_fuzzable_request("crawl"), "request")
        self.assertEqual(activity.latest_running_plugin(), ("crawl", "web_spider"))

    def test_clear_removes_current_activity(self):
        activity = StatusActivity()
        activity.set_running_plugin("audit", "sqli")
        activity.set_current_fuzzable_request("audit", "request")

        activity.clear()

        self.assertIsNone(activity.get_running_plugin("audit"))
        self.assertIsNone(activity.get_current_fuzzable_request("audit"))
        self.assertEqual(activity.latest_running_plugin(), ("audit", "sqli"))
