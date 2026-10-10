"""Adapt the request worker pool to the observed HTTP error rate."""

import threading
import time
from collections.abc import Callable
from typing import Protocol

from w3af.core.data.url.constants import ACCEPTABLE_ERROR_RATE


class AdjustableWorkerPool(Protocol):
    """Pool operations required by the concurrency policy."""

    def get_worker_count(self) -> int: ...

    def set_worker_count(self, worker_count: int) -> None: ...


class WorkerPoolAdjuster:
    """Increase or decrease workers using bounded, rate-limited adjustments."""

    def __init__(
        self,
        error_rate_provider: Callable[[], int],
        debug: Callable[[str], None],
    ) -> None:
        self._error_rate_provider = error_rate_provider
        self._debug = debug
        self._worker_pool_provider: Callable[[], AdjustableWorkerPool] | None = None
        self._min_worker_threads: int | None = None
        self._max_worker_threads: int | None = None
        self._last_call_to_adjust_workers: float | None = None
        self._should_adjust_workers_lock = threading.RLock()

    def configure(
        self,
        provider: Callable[[], AdjustableWorkerPool],
        min_workers: int,
        max_workers: int,
    ) -> None:
        self._worker_pool_provider = provider
        self._min_worker_threads = min_workers
        self._max_worker_threads = max_workers

    def adjust(self) -> None:
        if self._worker_pool_provider is None:
            return

        if not self._should_adjust_workers():
            return

        if self._should_decrease_worker_pool_size():
            self._decrease_worker_pool_size()
        elif self._should_increase_worker_pool():
            self._increase_worker_pool_size()

    def _decrease_worker_pool_size(self) -> None:
        worker_pool, min_workers = self._configured_pool_and_minimum()
        error_rate = self._error_rate_provider()

        new_worker_count = max(worker_pool.get_worker_count() - 2, min_workers)
        worker_pool.set_worker_count(new_worker_count)
        msg = "Decreased the worker pool size to %s (error rate: %i%%)"
        self._debug(msg % (new_worker_count, error_rate))

    def _increase_worker_pool_size(self) -> None:
        worker_pool, max_workers = self._configured_pool_and_maximum()
        error_rate = self._error_rate_provider()

        new_worker_count = min(worker_pool.get_worker_count() + 1, max_workers)
        worker_pool.set_worker_count(new_worker_count)
        msg = "Increased the worker pool size to %s (error rate: %i%%)"
        self._debug(msg % (new_worker_count, error_rate))

    def _should_increase_worker_pool(self) -> bool:
        error_rate = self._error_rate_provider()
        return error_rate < ACCEPTABLE_ERROR_RATE / 4.0

    def _should_decrease_worker_pool_size(self) -> bool:
        error_rate = self._error_rate_provider()
        return error_rate >= ACCEPTABLE_ERROR_RATE / 2.0

    def _should_adjust_workers(self) -> bool:
        with self._should_adjust_workers_lock:
            now = time.time()
            if (
                self._last_call_to_adjust_workers is None
                or now - self._last_call_to_adjust_workers >= 45
            ):
                self._last_call_to_adjust_workers = now
                return True

            return False

    def _configured_pool_and_minimum(
        self,
    ) -> tuple[AdjustableWorkerPool, int]:
        if self._worker_pool_provider is None or self._min_worker_threads is None:
            raise RuntimeError("Worker pool adjuster has not been configured")

        return self._worker_pool_provider(), self._min_worker_threads

    def _configured_pool_and_maximum(
        self,
    ) -> tuple[AdjustableWorkerPool, int]:
        if self._worker_pool_provider is None or self._max_worker_threads is None:
            raise RuntimeError("Worker pool adjuster has not been configured")

        return self._worker_pool_provider(), self._max_worker_threads
