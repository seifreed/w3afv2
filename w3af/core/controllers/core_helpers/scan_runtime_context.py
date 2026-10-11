"""Expose the runtime boundary required by scan strategies and consumers."""

from collections.abc import Callable
from typing import Any


class ScanRuntimeContext:
    """Provide scan services without exposing the core composition root."""

    def __init__(
        self,
        plugins: Any,
        uri_opener: Any,
        configuration: Any,
        database: Any,
        exception_handler: Any,
        worker_pool_provider: Callable[[], Any],
        is_404: Callable[[Any], bool],
    ) -> None:
        self.plugins = plugins
        self.uri_opener = uri_opener
        self.configuration = configuration
        self.database = database
        self.exception_handler = exception_handler
        self._worker_pool_provider = worker_pool_provider
        self._is_404 = is_404
        self._status: Any | None = None
        self._strategy: Any | None = None
        self._stop_callback: Callable[[], None] | None = None

    @property
    def worker_pool(self) -> Any:
        return self._worker_pool_provider()

    @property
    def status(self) -> Any:
        if self._status is None:
            raise RuntimeError("Scan status is not bound to the runtime context.")

        return self._status

    @property
    def strategy(self) -> Any:
        if self._strategy is None:
            raise RuntimeError("Scan strategy is not bound to the runtime context.")

        return self._strategy

    def bind_runtime(self, status: Any, strategy: Any) -> None:
        """Bind the status and strategy for the current scan run."""
        self._status = status
        self._strategy = strategy

    def get_status(self) -> Any:
        """Return the status provider required by lifecycle controllers."""
        return self.status

    def get_strategy(self) -> Any:
        """Return the strategy provider required by lifecycle controllers."""
        return self.strategy

    def bind_stop(self, stop_callback: Callable[[], None]) -> None:
        """Bind the scan stop operation after the controller is assembled."""
        self._stop_callback = stop_callback

    def stop(self) -> None:
        """Stop the active scan through the lifecycle controller."""
        if self._stop_callback is None:
            raise RuntimeError("Scan stop is not bound to the runtime context.")

        self._stop_callback()

    def is_404(self, response: Any) -> bool:
        """Check a response against the active scan's 404 fingerprint."""
        return self._is_404(response)
