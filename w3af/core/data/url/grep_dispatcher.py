"""Dispatch HTTP request/response pairs to the grep consumer."""

from collections.abc import Callable
from typing import Any


class GrepDispatcher:
    """Keep the optional grep callback outside the HTTP transport object."""

    def __init__(self) -> None:
        self._callback: Callable[[Any, Any], None] | None = None

    def set_callback(self, callback: Callable[[Any, Any], None] | None) -> None:
        self._callback = callback

    def dispatch(self, request: Any, response: Any) -> None:
        if self._callback is not None:
            self._callback(request, response)
