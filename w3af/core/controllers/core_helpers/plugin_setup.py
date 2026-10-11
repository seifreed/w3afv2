"""Prepare the configured plugin instances for a scan."""

from collections.abc import Callable
from typing import Protocol

from w3af.core.controllers.core_helpers.plugin_runtime import PluginRuntime
from w3af.core.controllers.core_helpers.plugin_selection import PluginSelection
from w3af.core.controllers.core_helpers.plugin_state import PluginState
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
        state: PluginState,
        set_mangle_plugins: Callable[[list[Plugin]], None],
    ) -> None:
        self._output_manager = output_manager
        self._selection = selection
        self._runtime = runtime
        self._state = state
        self._set_mangle_plugins = set_mangle_plugins

    def initialize(self) -> None:
        """Create all selected plugins and apply their scan configuration."""
        self._output_manager.set_output_plugins(self._selection.get("output"))
        self.create_instances()
        self._set_mangle_plugins(self._state.get_instances("mangle"))

    def create_instances(self) -> None:
        """Expand selections and create dependency-ordered instances."""
        self._selection.expand_all()
        self._selection.remove_exclusions()
        resolved_names = self._runtime.create_instances(
            self._selection.get_all(),
            self._state,
        )
        self._selection.replace_all(resolved_names)
