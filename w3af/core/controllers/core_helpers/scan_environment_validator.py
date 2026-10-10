"""Validate the preconditions required to start a scan."""

from w3af.core.exceptions import BaseFrameworkException


class ScanEnvironmentValidator:
    """Validate plugin and target configuration before scan execution."""

    def __init__(self, plugins, target) -> None:
        self._plugins = plugins
        self._target = target

    def validate(self) -> None:
        if not self._plugins.initialized:
            raise BaseFrameworkException(
                "You must call the plugins.init_plugins() method before"
                " calling start()."
            )

        if not self._target.has_valid_configuration():
            raise BaseFrameworkException("No target URI configured.")

        enabled_plugin_types = (
            "audit",
            "crawl",
            "infrastructure",
            "grep",
        )
        if not any(
            self._plugins.get_enabled_plugins(plugin_type)
            for plugin_type in enabled_plugin_types
        ):
            raise BaseFrameworkException(
                "No audit, grep or crawl plugins configured to run."
            )
