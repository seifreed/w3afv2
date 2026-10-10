"""Socket timeout state and adjustment policy for HTTP requests."""

import threading
import time

from w3af.core.data.url.constants import (
    DEFAULT_TIMEOUT,
    MAX_TIMEOUT,
    MIN_TIMEOUT,
    TIMEOUT_ADJUST_LIMIT,
    TIMEOUT_UPDATE_ELAPSED_MIN,
)


class TimeoutManager:
    """Keep configured and automatically adjusted socket timeouts."""

    def __init__(self, settings):
        self._settings = settings
        self._host_timeout = {}
        self._global_timeout = DEFAULT_TIMEOUT
        self._adjust_lock = threading.RLock()
        self._last_adjustment = 0.0

    def set_timeout(self, timeout, host):
        timeout = min(MAX_TIMEOUT, timeout)
        timeout = max(MIN_TIMEOUT, timeout)

        self._host_timeout[host] = timeout

    def get_timeout(self, host):
        return self._host_timeout.get(host, self._global_timeout)

    def clear(self):
        self._host_timeout = {}
        configured_timeout = self._settings.get_configured_timeout()
        self._global_timeout = (
            configured_timeout if configured_timeout != 0 else DEFAULT_TIMEOUT
        )

    def should_auto_adjust(self, total_requests):
        with self._adjust_lock:
            if self._settings.get_configured_timeout() != 0:
                return False

            if total_requests == 0:
                return False

            if total_requests % TIMEOUT_ADJUST_LIMIT != 0:
                return False

            elapsed = time.time() - self._last_adjustment
            if elapsed < TIMEOUT_UPDATE_ELAPSED_MIN:
                return False

            self._last_adjustment = time.time()
            return True
