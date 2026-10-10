"""Apply request evasion plugins in priority order."""

from collections.abc import Callable
from typing import Any

from w3af.core.exceptions import BaseFrameworkException


class RequestEvasionPipeline:
    """Manage request transformations supplied by evasion plugins."""

    def __init__(self, log_error: Callable[[str], None]) -> None:
        self._log_error = log_error
        self._plugins: list[Any] = []

    @property
    def plugins(self):
        return self._plugins

    def set_plugins(self, plugins) -> None:
        plugins.sort(key=lambda plugin: plugin.get_priority())
        self._plugins = plugins

    def apply(self, request):
        for plugin in self._plugins:
            try:
                request = plugin.modify_request(request)
            except BaseFrameworkException as error:
                message = (
                    f'Evasion plugin "{plugin.get_name()}" failed to modify '
                    f'the request: "{error}"'
                )
                self._log_error(message)

        return request
