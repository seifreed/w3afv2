"""Runtime services exposed to configured plugin instances."""

from collections.abc import Callable
from typing import Any


class PluginRuntimeContext:
    """Provide plugin services without retaining the core composition root."""

    def __init__(
        self,
        database: Any,
        uri_opener: Any,
        configuration: Any,
        knowledge_base: Any,
        parser_cache: Any,
        id_generator: Any,
        exception_handler: Any,
        worker_pool_provider: Callable[[], Any],
        is_404: Callable[[Any], bool],
    ) -> None:
        self.database = database
        self.uri_opener = uri_opener
        self.configuration = configuration
        self.knowledge_base = knowledge_base
        self.parser_cache = parser_cache
        self.id_generator = id_generator
        self.exception_handler = exception_handler
        self._worker_pool_provider = worker_pool_provider
        self._is_404 = is_404
        self._status: Any | None = None

    @property
    def worker_pool(self) -> Any:
        return self._worker_pool_provider()

    @property
    def status(self) -> Any:
        if self._status is None:
            raise RuntimeError("Plugin status is not bound to the runtime context.")

        return self._status

    def bind_status(self, status: Any) -> None:
        """Bind the status object for the current scan."""
        self._status = status

    def is_404(self, response: Any) -> bool:
        """Check a response against the scan's 404 fingerprint."""
        return self._is_404(response)
