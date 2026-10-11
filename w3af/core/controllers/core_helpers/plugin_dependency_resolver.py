"""Resolve and order enabled plugins according to their dependencies."""

from collections import deque
from collections.abc import Callable
from typing import Protocol


class PluginWithDependencies(Protocol):
    """Runtime plugin contract required by dependency resolution."""

    def get_plugin_deps(self) -> list[str]:
        """Return plugin dependencies as ``type.name`` values."""

        ...


class PluginDependencyResolver:
    """Apply dependency expansion and ordering to enabled plugin names."""

    def __init__(
        self,
        plugin_names: dict[str, list[str]],
        instance_provider: Callable[[str, str], PluginWithDependencies],
        report: Callable[[str], None],
    ) -> None:
        self._plugin_names = plugin_names
        self._instance_provider = instance_provider
        self._report = report

    def resolve(self) -> None:
        """Enable every dependency required by the selected plugins."""
        pending_plugins = deque(
            [
                (plugin_type, plugin_name)
                for plugin_type, enabled_plugins in self._plugin_names.items()
                for plugin_name in enabled_plugins
            ]
        )
        resolved_plugins = set()

        while pending_plugins:
            plugin_type, plugin_name = pending_plugins.popleft()
            plugin_key = (plugin_type, plugin_name)
            if plugin_key in resolved_plugins:
                continue

            resolved_plugins.add(plugin_key)
            for dependency in self._dependencies_for(plugin_type, plugin_name):
                dependency_type, dependency_name = self._parse_dependency(dependency)

                if dependency_name not in self._plugin_names[dependency_type]:
                    self._report(
                        f"Enabling {plugin_name}'s dependency {dependency_name}"
                    )
                    self._plugin_names[dependency_type].append(dependency_name)

                pending_plugins.append((dependency_type, dependency_name))

    def order(self) -> None:
        """Place same-type dependencies before their dependants."""
        for plugin_type, enabled_plugins in self._plugin_names.items():
            self._plugin_names[plugin_type] = self._order_plugin_type(
                plugin_type, enabled_plugins
            )

    def _order_plugin_type(
        self, plugin_type: str, enabled_plugins: list[str]
    ) -> list[str]:
        ordered_plugins: list[str] = []
        visited_plugins: set[str] = set()
        visiting_plugins: set[str] = set()

        for plugin_name in enabled_plugins:
            self._visit_plugin(
                plugin_type,
                plugin_name,
                enabled_plugins,
                ordered_plugins,
                visited_plugins,
                visiting_plugins,
            )

        return ordered_plugins

    def _visit_plugin(
        self,
        plugin_type: str,
        plugin_name: str,
        enabled_plugins: list[str],
        ordered_plugins: list[str],
        visited_plugins: set[str],
        visiting_plugins: set[str],
    ) -> None:
        if plugin_name in visited_plugins:
            return
        if plugin_name in visiting_plugins:
            raise ValueError(f"Cyclic dependency involving {plugin_name}")

        visiting_plugins.add(plugin_name)
        for dependency in self._dependencies_for(plugin_type, plugin_name):
            dependency_type, dependency_name = self._parse_dependency(dependency)
            if dependency_type == plugin_type:
                if dependency_name not in enabled_plugins:
                    raise ValueError(
                        f"Missing dependency {dependency} for {plugin_name}"
                    )
                self._visit_plugin(
                    plugin_type,
                    dependency_name,
                    enabled_plugins,
                    ordered_plugins,
                    visited_plugins,
                    visiting_plugins,
                )

        visiting_plugins.remove(plugin_name)
        visited_plugins.add(plugin_name)
        ordered_plugins.append(plugin_name)

    def _dependencies_for(self, plugin_type: str, plugin_name: str) -> list[str]:
        plugin_instance = self._instance_provider(plugin_type, plugin_name)
        return plugin_instance.get_plugin_deps()

    @staticmethod
    def _parse_dependency(dependency: str) -> tuple[str, str]:
        dependency_parts = dependency.split(".")
        if len(dependency_parts) != 2 or not all(dependency_parts):
            raise ValueError(
                f"Invalid plugin dependency {dependency!r}; expected 'type.name'"
            )
        return dependency_parts[0], dependency_parts[1]
