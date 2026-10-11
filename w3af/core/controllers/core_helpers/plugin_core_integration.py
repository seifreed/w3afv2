"""Bridge plugin runtime configuration to the core-owned opener."""

from typing import Protocol

from w3af.core.controllers.plugins.plugin import Plugin


class PluginOpenerSettings(Protocol):
    """Opener settings needed by mangle plugins."""

    def set_mangle_plugins(self, plugins: list[Plugin]) -> None: ...


class PluginOpener(Protocol):
    """Opener operations used by plugin integration."""

    settings: PluginOpenerSettings

    def set_evasion_plugins(self, plugins: list[Plugin]) -> None: ...


class PluginIntegrationContext(Protocol):
    """Core services exposed to the plugin integration boundary."""

    database: object
    uri_opener: PluginOpener


class PluginCoreIntegration:
    """Apply plugin runtime dependencies to the owning core."""

    def __init__(self, context: PluginIntegrationContext | None) -> None:
        self._context = context

    def get_database(self) -> object | None:
        if self._context is None:
            return None
        return self._context.database

    def set_evasion_plugins(self, plugins: list[Plugin]) -> None:
        if self._context is not None:
            self._context.uri_opener.set_evasion_plugins(plugins)

    def set_mangle_plugins(self, plugins: list[Plugin]) -> None:
        if self._context is not None:
            self._context.uri_opener.settings.set_mangle_plugins(plugins)
