"""Tests for deterministic plugin dependency resolution."""

import unittest

from w3af.core.controllers.core_helpers.plugin_dependency_resolver import (
    PluginDependencyResolver,
)


class DependencyPlugin:
    def __init__(self, dependencies):
        self._dependencies = dependencies

    def get_plugin_deps(self):
        return self._dependencies


class TestPluginDependencyResolver(unittest.TestCase):
    def resolver(self, plugin_names, dependencies):
        provider = {key: DependencyPlugin(value) for key, value in dependencies.items()}
        reports: list[str] = []
        resolver = PluginDependencyResolver(
            plugin_names,
            lambda plugin_type, plugin_name: provider[(plugin_type, plugin_name)],
            reports.append,
        )
        return resolver, reports

    def test_resolve_adds_transitive_dependencies_once(self):
        plugin_names = {"audit": ["top"], "grep": []}
        dependencies = {
            ("audit", "top"): ["grep.middle"],
            ("grep", "middle"): ["grep.leaf"],
            ("grep", "leaf"): [],
        }
        resolver, reports = self.resolver(plugin_names, dependencies)

        resolver.resolve()

        self.assertEqual(plugin_names, {"audit": ["top"], "grep": ["middle", "leaf"]})
        self.assertEqual(
            reports,
            [
                "Enabling top's dependency middle",
                "Enabling middle's dependency leaf",
            ],
        )

    def test_order_resolves_transitive_same_type_dependencies(self):
        plugin_names = {"audit": ["top", "middle", "leaf"]}
        dependencies = {
            ("audit", "top"): ["audit.middle"],
            ("audit", "middle"): ["audit.leaf"],
            ("audit", "leaf"): [],
        }
        resolver, _ = self.resolver(plugin_names, dependencies)

        resolver.order()

        self.assertEqual(plugin_names["audit"], ["leaf", "middle", "top"])

    def test_order_rejects_cycles(self):
        plugin_names = {"audit": ["first", "second"]}
        dependencies = {
            ("audit", "first"): ["audit.second"],
            ("audit", "second"): ["audit.first"],
        }
        resolver, _ = self.resolver(plugin_names, dependencies)

        with self.assertRaisesRegex(ValueError, "Cyclic dependency"):
            resolver.order()

    def test_invalid_dependency_has_actionable_error(self):
        plugin_names = {"audit": ["broken"]}
        dependencies = {("audit", "broken"): ["malformed"]}
        resolver, _ = self.resolver(plugin_names, dependencies)

        with self.assertRaisesRegex(ValueError, "expected 'type.name'"):
            resolver.resolve()
