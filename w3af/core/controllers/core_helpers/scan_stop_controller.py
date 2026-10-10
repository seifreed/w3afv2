"""Coordinate the graceful stop of a running scan."""

import time
from collections.abc import Callable
from typing import Protocol

from w3af.core.controllers.misc.epoch_to_string import epoch_to_string


class Stoppable(Protocol):
    """Object that can stop its work."""

    def stop(self) -> None: ...


class RunningStatus(Protocol):
    """Status information required while stopping a scan."""

    def is_running(self) -> bool: ...


class DebugOutput(Protocol):
    """Output operation used by the stop workflow."""

    def debug(self, message: str) -> None: ...


class ScanStopController:
    """Stop request processing and worker cleanup for one scan runtime."""

    def __init__(
        self,
        output: DebugOutput,
        uri_opener: Stoppable,
        strategy_provider: Callable[[], Stoppable | None],
        status_provider: Callable[[], RunningStatus],
        terminate_worker_pool: Callable[[], None],
        timeout_provider: Callable[[], float],
        loop_delay_provider: Callable[[], float],
    ) -> None:
        self._output = output
        self._uri_opener = uri_opener
        self._strategy_provider = strategy_provider
        self._status_provider = status_provider
        self._terminate_worker_pool = terminate_worker_pool
        self._timeout_provider = timeout_provider
        self._loop_delay_provider = loop_delay_provider

    def stop(self) -> None:
        """Request a stop, wait briefly, and terminate the worker pool."""
        self._output.debug("The user stopped the core, finishing threads...")
        self._uri_opener.stop()

        strategy = self._strategy_provider()
        if strategy is not None:
            strategy.stop()

        self._wait_for_scan_stop()
        self._terminate_worker_pool()

    def _wait_for_scan_stop(self) -> None:
        timeout = self._timeout_provider()
        loop_delay = self._loop_delay_provider()
        stop_start_time = time.time()

        for _ in range(int(timeout / loop_delay)):
            if not self._status_provider().is_running():
                core_stop_time = epoch_to_string(stop_start_time)
                msg = f"{core_stop_time} were needed to stop the core."
                break

            try:
                time.sleep(loop_delay)
            except KeyboardInterrupt:
                msg = "The user cancelled the cleanup process, forcing exit."
                break
        else:
            msg = f"The core failed to stop in {timeout} seconds, forcing exit."

        self._output.debug(msg)
