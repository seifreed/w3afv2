"""
Lifecycle state for a scan status.
"""

import time

from w3af.core.controllers.misc.epoch_to_string import epoch_to_string


class StatusLifecycle:
    """Track scan state and elapsed time without controller dependencies."""

    def __init__(self, scans_completed=0):
        self._is_running = False
        self._paused = False
        self._start_time_epoch = None
        self.scans_completed = scans_completed

    @property
    def start_time_epoch(self):
        return self._start_time_epoch

    @start_time_epoch.setter
    def start_time_epoch(self, value):
        self._start_time_epoch = value

    def pause(self, pause_yes_no):
        self._paused = pause_yes_no
        self._is_running = not pause_yes_no

    def start(self):
        self._is_running = True
        self._start_time_epoch = time.time()

    def stop(self):
        self._is_running = False

    def is_running(self):
        return self._is_running

    def is_paused(self):
        return self._paused

    def has_started(self):
        return self._start_time_epoch is not None

    def get_run_time(self):
        if self._start_time_epoch is None:
            raise RuntimeError("Can NOT call get_run_time before start().")

        return (time.time() - self._start_time_epoch) / 60

    def get_run_time_seconds(self):
        if self._start_time_epoch is None:
            raise RuntimeError("Can NOT call get_run_time before start().")

        return time.time() - self._start_time_epoch

    def get_scan_time(self):
        return epoch_to_string(self._start_time_epoch)

    def scan_finished(self):
        self._is_running = False
        self.scans_completed += 1
