"""Delay requests when the observed HTTP error rate is too high."""

import threading
from collections.abc import Callable

from w3af.core.data.url.constants import (
    ACCEPTABLE_ERROR_RATE,
    ERROR_DELAY_LIMIT,
    SOCKET_ERROR_DELAY,
)


class HttpErrorPauseController:
    """Apply one progressive delay per observed error-rate bucket."""

    def __init__(
        self,
        error_rate_provider: Callable[[], int],
        request_count_provider: Callable[[], int],
        sleep: Callable[[float], None],
        debug: Callable[[str], None],
    ) -> None:
        self._error_rate_provider = error_rate_provider
        self._request_count_provider = request_count_provider
        self._sleep = sleep
        self._debug = debug
        self._error_pause_lock = threading.RLock()
        self._sleep_log: dict[int, bool] = {}
        self.clear()

    @property
    def sleep_log(self):
        return self._sleep_log

    def clear(self) -> None:
        self._sleep_log = {}

        step = ACCEPTABLE_ERROR_RATE * 2
        self._sleep_log.update((i, False) for i in range(0, 110, step))

    def pause_on_error(self, request) -> None:
        """Delay a request once per error-rate bucket when needed."""
        with self._error_pause_lock:
            error_rate = self._error_rate_provider()
            if not self._should_pause(error_rate):
                return

            pending_pause, lower_error_rate = self._has_pending_pause(error_rate)
            if not pending_pause:
                return

            error_sleep = SOCKET_ERROR_DELAY * error_rate
            msg = (
                "Sleeping for %s seconds before sending HTTP request to"
                ' "%s" (did:%s) after receiving URL/socket error. The ExtendedUrllib'
                " error rate is at %s%%"
            )
            args = (error_sleep, request.url_object, request.debugging_id, error_rate)
            self._debug(msg % args)

            self._sleep(error_sleep)
            self._sleep_log[lower_error_rate] = True

            if self._request_count_provider() % 100 == 0:
                self.clear()

    def _has_pending_pause(self, error_rate):
        step = ACCEPTABLE_ERROR_RATE * 2
        lower_error_rate = divmod(error_rate, step)[0] * step
        return not self._sleep_log[lower_error_rate], lower_error_rate

    def _should_pause(self, error_rate):
        if error_rate <= ACCEPTABLE_ERROR_RATE:
            return False

        return self._request_count_provider() % ERROR_DELAY_LIMIT == 0
