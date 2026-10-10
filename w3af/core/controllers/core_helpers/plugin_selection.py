"""Manage the names of plugins enabled for a scan."""

from collections.abc import Callable


class PluginSelection:
    """Validate and normalize plugin names before instance creation."""

    def __init__(self, plugin_list_provider: Callable[[str], list[str]]) -> None:
        self._plugin_list_provider = plugin_list_provider
        self.names: dict[str, list[str]] = {}

    def reset(self, plugin_types: list[str]) -> None:
        self.names = {plugin_type: [] for plugin_type in plugin_types}

    def set_plugins(
        self, plugin_names, plugin_type: str, raise_on_error: bool = True
    ) -> list[str]:
        unique_names = list(dict.fromkeys(plugin_names))
        known_names = self._plugin_list_provider(plugin_type)
        unknown_plugins = []

        for plugin_name in unique_names:
            if (
                plugin_name not in known_names
                and plugin_name.replace("!", "") not in known_names
                and plugin_name != "all"
            ):
                if raise_on_error:
                    raise ValueError(f"Unknown plugin {plugin_name}")
                unknown_plugins.append(plugin_name)

        self.names[plugin_type] = [
            plugin_name
            for plugin_name in unique_names
            if plugin_name not in unknown_plugins
        ]
        return unknown_plugins

    def expand_all(self) -> None:
        for plugin_type, enabled_plugins in self.names.items():
            if "all" not in enabled_plugins:
                continue

            enabled_plugins.extend(self._plugin_list_provider(plugin_type))
            self.names[plugin_type] = list(dict.fromkeys(enabled_plugins))
            self.names[plugin_type].remove("all")

    def remove_exclusions(self) -> None:
        for plugin_type, enabled_plugins in self.names.items():
            excluded_plugins = {
                plugin_name[1:]
                for plugin_name in enabled_plugins
                if plugin_name.startswith("!")
            }
            self.names[plugin_type] = [
                plugin_name
                for plugin_name in enabled_plugins
                if not plugin_name.startswith("!")
                and plugin_name not in excluded_plugins
            ]
