"""Assemble the plugin instances used by a scan."""

import logging
from collections.abc import Callable

from w3af.core.controllers.core_helpers.plugin_dependency_resolver import (
    PluginDependencyResolver,
    PluginWithDependencies,
)
from w3af.core.controllers.core_helpers.plugin_state import PluginState
from w3af.core.controllers.plugins.plugin import Plugin

LOGGER = logging.getLogger(__name__)


class PluginRuntime:
    """Resolve plugin dependencies and keep the active instances in sync."""

    def __init__(
        self,
        plugin_instance_provider: Callable[[str, str], Plugin],
        quick_instance_provider: Callable[[str, str], PluginWithDependencies],
        report: Callable[[str], None],
    ) -> None:
        self._plugin_instance_provider = plugin_instance_provider
        self._quick_instance_provider = quick_instance_provider
        self._report = report
        self._ended_instances: set[int] = set()

    def create_instances(
        self,
        plugin_names: dict[str, list[str]],
        state: PluginState,
    ) -> dict[str, list[str]]:
        """Resolve dependencies and create the instances for each plugin type."""
        resolver = PluginDependencyResolver(
            plugin_names,
            self._quick_instance_provider,
            self._report,
        )
        resolver.resolve()
        resolver.order()

        for plugin_type, enabled_plugins in plugin_names.items():
            for plugin_name in enabled_plugins:
                plugin_instance = self._plugin_instance_provider(
                    plugin_type, plugin_name
                )
                state.add_or_update_instance(
                    plugin_type,
                    plugin_name,
                    plugin_instance,
                )

        return plugin_names

    def mark_instance_ended(self, plugin_instance: Plugin) -> None:
        """Remember that another lifecycle owner already ended an instance."""
        self._ended_instances.add(id(plugin_instance))

    def release_instances(self, state: PluginState) -> None:
        """End every active plugin and clear the references it owns."""
        first_exception = None
        for plugin_instances in state.get_all_instances().values():
            for plugin_instance in plugin_instances:
                if id(plugin_instance) in self._ended_instances:
                    continue
                try:
                    plugin_instance.end()
                except Exception as exception:
                    LOGGER.debug("Plugin cleanup failed", exc_info=True)
                    if first_exception is None:
                        first_exception = exception
        state.clear_instances()

        self._ended_instances.clear()

        if first_exception is not None:
            raise first_exception
