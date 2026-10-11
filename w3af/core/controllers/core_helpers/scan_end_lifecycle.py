"""Finalize a scan while preserving the core's dependency order."""

from collections.abc import Callable
from typing import Protocol


class DebugOutput(Protocol):
    """Output operation required by scan finalization."""

    def debug(self, message: str) -> None: ...


class OutputManager(Protocol):
    """Output manager operation required by scan finalization."""

    def end_output_plugins(self) -> None: ...


class Clearable(Protocol):
    """Resource that can clear its scan state."""

    def clear(self) -> None: ...


class ScanEndLifecycle:
    """Release scan resources in the order required by their dependencies."""

    def __init__(
        self,
        output: DebugOutput,
        output_manager: OutputManager,
        parser_cache: Clearable,
        stop_profiling: Callable[[], None],
        terminate_worker_pool: Callable[[], None],
        prepare_exploit_phase: Callable[[], None],
        release_plugins: Callable[[], None],
        clear_target: Callable[[], None],
        stop_status: Callable[[], None],
    ) -> None:
        self._output = output
        self._output_manager = output_manager
        self._parser_cache = parser_cache
        self._stop_profiling = stop_profiling
        self._terminate_worker_pool = terminate_worker_pool
        self._prepare_exploit_phase = prepare_exploit_phase
        self._release_plugins = release_plugins
        self._clear_target = clear_target
        self._stop_status = stop_status

    def finish(self) -> None:
        """Finalize the scan even when output plugin cleanup raises."""
        self._stop_profiling()
        self._parser_cache.clear()

        try:
            self._output.debug("Calling end_output_plugins()")
            self._output_manager.end_output_plugins()
        finally:
            self._terminate_worker_pool()
            self._prepare_exploit_phase()
            self._release_plugins()
            self._clear_target()
            self._stop_status()

        self._output.debug("scan_end_hook() completed")
