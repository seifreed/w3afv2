"""Prepare the resources and runtime required by a scan."""

import threading
from collections.abc import Callable
from typing import Protocol


class ScanStatus(Protocol):
    """Status operations required while starting a scan."""

    scans_completed: int

    def start(self) -> None: ...


class ScanStrategy(Protocol):
    """Strategy operation required while starting a scan."""

    def add_observer(self, observer: object) -> None: ...


class ScanStartLifecycle:
    """Own scan-start state and the profiling session attached to it."""

    def __init__(
        self,
        get_status: Callable[[], ScanStatus],
        get_strategy: Callable[[], ScanStrategy],
        start_profiling: Callable[[], list[threading.Timer]],
        stop_profiling: Callable[[list[threading.Timer]], None],
        cleanup_previous_scan: Callable[[], None],
        prepare_directories: Callable[[], None],
        create_scan_runtime: Callable[[int], None],
        add_observers: Callable[[ScanStrategy], None],
        start_fingerprint_detector: Callable[[], None],
    ) -> None:
        self._get_status = get_status
        self._get_strategy = get_strategy
        self._start_profiling = start_profiling
        self._stop_profiling_callback = stop_profiling
        self._cleanup_previous_scan = cleanup_previous_scan
        self._prepare_directories = prepare_directories
        self._create_scan_runtime = create_scan_runtime
        self._add_observers = add_observers
        self._start_fingerprint_detector = start_fingerprint_detector
        self._first_scan = True
        self._profiling_timers: list[threading.Timer] = []
        self._profiling_active = False

    def start(self) -> None:
        """Prepare a fresh runtime for the next scan."""
        self.stop_profiling()
        scans_completed = self._get_status().scans_completed
        self._profiling_timers = self._start_profiling()
        self._profiling_active = True

        if self._first_scan:
            self._prepare_directories()
        else:
            self._cleanup_previous_scan()

        self._create_scan_runtime(scans_completed)
        status = self._get_status()
        status.start()
        self._add_observers(self._get_strategy())
        self._start_fingerprint_detector()

    def mark_scan_started(self) -> None:
        """Record that environment validation completed for the scan."""
        self._first_scan = False

    def stop_profiling(self) -> None:
        """Stop profiling once, including aborted scans."""
        if not self._profiling_active:
            return

        self._stop_profiling_callback(self._profiling_timers)
        self._profiling_timers = []
        self._profiling_active = False
