"""Request rate limiting policy for HTTP traffic."""

import threading
import time


class RateLimiter:
    """Enforce the configured maximum number of requests per second."""

    def __init__(self, settings, sleep):
        self._settings = settings
        self._sleep = sleep
        self._last_time_called = 0.0
        self._lock = threading.RLock()

    def wait(self):
        max_requests_per_second = self._settings.get_max_requests_per_second()

        if max_requests_per_second <= 0:
            return

        min_interval = 1.0 / float(max_requests_per_second)
        elapsed = time.monotonic() - self._last_time_called
        left_to_wait = min_interval - elapsed

        with self._lock:
            if left_to_wait > 0:
                self._sleep(left_to_wait)

        self._last_time_called = time.monotonic()
