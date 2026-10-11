"""Coordinate pausing the scan and its HTTP requests."""

from collections.abc import Callable
from typing import Protocol


class Pausable(Protocol):
    """Object that can pause and resume its work."""

    def pause(self, pause_yes_no: bool) -> None: ...


class ScanPauseController:
    """Keep scan status and request activity in the same pause state."""

    def __init__(
        self, status_provider: Callable[[], Pausable], uri_opener: Pausable
    ) -> None:
        self._status_provider = status_provider
        self._uri_opener = uri_opener

    def pause(self, pause_yes_no: bool) -> None:
        """Pause or resume both scan coordination and HTTP requests."""
        self._status_provider().pause(pause_yes_no)
        self._uri_opener.pause(pause_yes_no)
