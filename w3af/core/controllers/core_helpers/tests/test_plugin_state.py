"""Tests for the plugin state boundary."""

import unittest

from w3af.core.controllers.core_helpers.plugin_state import PluginState
from w3af.core.controllers.plugins.plugin import Plugin


class TestPluginState(unittest.TestCase):
    def setUp(self):
        self.state = PluginState()
        self.state.reset(["crawl", "mangle"])

    def test_reset_creates_empty_runtime_and_attack_options(self):
        self.assertEqual(self.state.get_instances("crawl"), [])
        self.assertEqual(self.state.get_all_plugin_options()["attack"], {})

    def test_options_are_returned_as_snapshots(self):
        options = {"enabled": True}
        self.state.set_plugin_options("crawl", "spider", options)

        snapshot = self.state.get_all_plugin_options()
        snapshot["crawl"]["spider"] = {"enabled": False}

        self.assertEqual(self.state.get_plugin_options("crawl", "spider"), options)

    def test_instances_are_returned_as_snapshots(self):
        plugin = Plugin()
        self.state.set_instances("crawl", [plugin])

        snapshot = self.state.get_instances("crawl")
        snapshot.clear()

        self.assertEqual(self.state.get_instances("crawl"), [plugin])

    def test_clear_instances_releases_all_references(self):
        self.state.set_instances("crawl", [Plugin()])

        self.state.clear_instances()

        self.assertEqual(self.state.get_all_instances(), {"crawl": [], "mangle": []})
