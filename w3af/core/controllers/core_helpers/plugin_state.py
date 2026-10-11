"""Own the mutable plugin options and runtime instances."""

from typing import Any

from w3af.core.controllers.plugins.plugin import Plugin


class PluginState:
    """Keep plugin configuration and instances behind one explicit boundary."""

    def __init__(self) -> None:
        self._options: dict[str, dict[str, Any]] = {}
        self._instances: dict[str, list[Plugin]] = {}

    def reset(self, plugin_types: list[str]) -> None:
        self._options = {plugin_type: {} for plugin_type in plugin_types}
        self._options["attack"] = {}
        self._instances = {plugin_type: [] for plugin_type in plugin_types}

    def get_plugin_options(self, plugin_type: str, plugin_name: str) -> Any:
        return self._options.get(plugin_type, {}).get(plugin_name)

    def has_plugin_options(self, plugin_type: str, plugin_name: str) -> bool:
        return plugin_name in self._options.get(plugin_type, {})

    def set_plugin_options(
        self, plugin_type: str, plugin_name: str, plugin_options: Any
    ) -> None:
        self._options[plugin_type][plugin_name] = plugin_options

    def get_all_plugin_options(self) -> dict[str, dict[str, Any]]:
        return {
            plugin_type: dict(plugin_options)
            for plugin_type, plugin_options in self._options.items()
        }

    def get_instances(self, plugin_type: str) -> list[Plugin]:
        return list(self._instances[plugin_type])

    def set_instances(self, plugin_type: str, plugins: list[Plugin]) -> None:
        self._instances[plugin_type] = list(plugins)

    def get_all_instances(self) -> dict[str, list[Plugin]]:
        return {
            plugin_type: list(plugin_instances)
            for plugin_type, plugin_instances in self._instances.items()
        }

    def add_or_update_instance(
        self,
        plugin_type: str,
        plugin_name: str,
        plugin_instance: Plugin,
    ) -> None:
        active_plugins = self._instances[plugin_type]
        if plugin_instance not in active_plugins:
            active_plugins.append(plugin_instance)
            return

        if not self.has_plugin_options(plugin_type, plugin_name):
            return

        plugin_options = self.get_plugin_options(plugin_type, plugin_name)
        for existing_instance in active_plugins:
            if existing_instance.get_name() == plugin_name:
                existing_instance.set_options(plugin_options)
                return

    def clear_instances(self) -> None:
        for plugin_instances in self._instances.values():
            plugin_instances.clear()
