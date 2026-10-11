"""Prepare the configured plugin instances for a scan."""

from collections.abc import Callable
from typing import Any, Protocol

from w3af.core.controllers.core_helpers.plugin_runtime import PluginRuntime
from w3af.core.controllers.core_helpers.plugin_selection import PluginSelection
from w3af.core.controllers.plugins.plugin import Plugin


class OutputPluginManager(Protocol):
    def set_output_plugins(self, output_plugins: list[str]) -> None: ...


class PluginSetup:
    """Resolve plugin selections and create their runtime instances."""

    def __init__(
        self,
        output_manager: OutputPluginManager,
        selection: PluginSelection,
        runtime: PluginRuntime,
        get_plugin_options: Callable[[], dict[str, dict[str, Any]]],
        get_plugin_instances: Callable[[], dict[str, list[Plugin]]],
        get_instances_by_type: Callable[[str], list[Plugin]],
        set_mangle_plugins: Callable[[list[Plugin]], None],
    ) -> None:
        self._output_manager = output_manager
        self._selection = selection
        self._runtime = runtime
        self._get_plugin_options = get_plugin_options
        self._get_plugin_instances = get_plugin_instances
        self._get_instances_by_type = get_instances_by_type
        self._set_mangle_plugins = set_mangle_plugins

    def initialize(self) -> None:
        """Create all selected plugins and apply their scan configuration."""
        self._output_manager.set_output_plugins(self._selection.get("output"))
        self.create_instances()
        self._set_mangle_plugins(self._get_instances_by_type("mangle"))

    def create_instances(self) -> None:
        """Expand selections and create dependency-ordered instances."""
        self._selection.expand_all()
        self._selection.remove_exclusions()
        resolved_names = self._runtime.create_instances(
            self._selection.get_all(),
            self._get_plugin_options(),
            self._get_plugin_instances(),
        )
        self._selection.replace_all(resolved_names)
