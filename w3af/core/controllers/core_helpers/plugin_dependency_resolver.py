"""Resolve and order enabled plugins according to their dependencies."""

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
        for plugin_type, enabled_plugins in self._plugin_names.items():
            for plugin_name in enabled_plugins:
                plugin_instance = self._instance_provider(plugin_type, plugin_name)

                for dependency in plugin_instance.get_plugin_deps():
                    dependency_type, dependency_name = dependency.split(".")

                    if dependency_name in self._plugin_names[dependency_type]:
                        continue

                    self._report(
                        f"Enabling {plugin_name}'s dependency {dependency_name}"
                    )
                    self._plugin_names[dependency_type].append(dependency_name)
                    self.resolve()

    def order(self) -> None:
        """Place same-type dependencies before their dependants."""
        for plugin_type, enabled_plugins in self._plugin_names.items():
            for plugin_name in enabled_plugins:
                plugin_instance = self._instance_provider(plugin_type, plugin_name)

                for dependency in plugin_instance.get_plugin_deps():
                    dependency_type, dependency_name = dependency.split(".")

                    if dependency_type != plugin_type:
                        continue

                    plugin_index = enabled_plugins.index(plugin_name)
                    dependency_index = enabled_plugins.index(dependency_name)

                    if dependency_index < plugin_index:
                        continue

                    enabled_plugins[plugin_index] = dependency_name
                    enabled_plugins[dependency_index] = plugin_name
