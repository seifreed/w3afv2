"""Manage request mode changes that affect reusable HTTP state."""

from collections.abc import Callable


class RequestModeController:
    """Keep exploit mode and reset state affected by that mode."""

    def __init__(
        self,
        clear_timeout: Callable[[], None],
        close_connections: Callable[[], None],
    ) -> None:
        self._clear_timeout = clear_timeout
        self._close_connections = close_connections
        self._exploit_mode = False

    @property
    def exploit_mode(self) -> bool:
        return self._exploit_mode

    def set_exploit_mode(self, exploit_mode: bool) -> None:
        self._exploit_mode = exploit_mode
        self._clear_timeout()
        self._close_connections()
