"""Reset scan state while keeping core-owned resources reusable."""

from collections.abc import Callable
from typing import Protocol


class Restartable(Protocol):
    def restart(self) -> None: ...


class Clearable(Protocol):
    def clear(self) -> None: ...


class ResettableKnowledgeBase(Protocol):
    def cleanup(self) -> None: ...


class ResettableExceptionHandler(Protocol):
    def clear(self) -> None: ...


class ResettableFingerprint(Protocol):
    def cleanup(self) -> None: ...


class ScanResetLifecycle:
    """Clear the state that must not survive into the next scan."""

    def __init__(
        self,
        uri_opener: Restartable,
        reset_exploit_mode: Callable[[], None],
        exception_handler: ResettableExceptionHandler,
        knowledge_base: ResettableKnowledgeBase,
        parser_cache: Clearable,
        fingerprint_404: ResettableFingerprint,
        dns_cache: Clearable,
        remove_temp_dir: Callable[[], None],
    ) -> None:
        self._uri_opener = uri_opener
        self._reset_exploit_mode = reset_exploit_mode
        self._exception_handler = exception_handler
        self._knowledge_base = knowledge_base
        self._parser_cache = parser_cache
        self._fingerprint_404 = fingerprint_404
        self._dns_cache = dns_cache
        self._remove_temp_dir = remove_temp_dir

    def reset(self) -> None:
        """Release scan data without closing the reusable core."""
        self._uri_opener.restart()
        self._reset_exploit_mode()
        self._exception_handler.clear()
        self._knowledge_base.cleanup()
        self._parser_cache.clear()
        self._fingerprint_404.cleanup()
        self._dns_cache.clear()
        self._remove_temp_dir()
