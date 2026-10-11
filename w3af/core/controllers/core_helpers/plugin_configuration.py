"""Apply and expose the options configured for plugin instances."""

from collections.abc import Callable
from typing import Any, Protocol

from w3af.core.controllers.core_helpers.plugin_state import PluginState
from w3af.core.controllers.plugins.plugin import Plugin


class OutputPluginManager(Protocol):
    """Output service needed to retain output-plugin options."""

    def set_plugin_options(self, plugin_name: str, plugin_options: Any) -> None: ...


class PluginConfiguration:
    """Coordinate persisted plugin options with their live instances."""

    def __init__(
        self,
        output_manager: OutputPluginManager,
        state: PluginState,
        plugin_provider: Callable[[str, str], Plugin],
    ) -> None:
        self._output_manager = output_manager
        self._state = state
        self._plugin_provider = plugin_provider

    def set(self, plugin_type: str, plugin_name: str, plugin_options: Any) -> None:
        """Store options and apply them to the corresponding plugin instance."""
        if plugin_type.lower() == "output":
            self._output_manager.set_plugin_options(plugin_name, plugin_options)

        self._state.set_plugin_options(plugin_type, plugin_name, plugin_options)
        self._plugin_provider(plugin_type, plugin_name).set_options(plugin_options)

    def get(self, plugin_type: str, plugin_name: str) -> Any:
        """Return options previously configured for a plugin."""
        return self._state.get_plugin_options(plugin_type, plugin_name)

    def get_all(self) -> dict[str, dict[str, Any]]:
        """Return a snapshot of every configured plugin option set."""
        return self._state.get_all_plugin_options()
