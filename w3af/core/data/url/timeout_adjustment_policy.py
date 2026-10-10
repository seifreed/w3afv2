"""Adjust request timeouts using observed response times and failures."""

from w3af.core.data.url.constants import (
    TIMEOUT_ADJUST_LIMIT,
    TIMEOUT_INCREASE_MULT,
    TIMEOUT_MULT_CONST,
)


class TimeoutAdjustmentPolicy:
    """Apply automatic timeout calibration during a scan."""

    def __init__(
        self,
        timeout_manager,
        get_average_rtt,
        get_total_requests,
        set_timeout,
        get_timeout,
        log_debug,
    ) -> None:
        self._timeout_manager = timeout_manager
        self._get_average_rtt = get_average_rtt
        self._get_total_requests = get_total_requests
        self._set_timeout = set_timeout
        self._get_timeout = get_timeout
        self._log_debug = log_debug

    def adjust(self, request) -> None:
        if not self._timeout_manager.should_auto_adjust(self._get_total_requests()):
            return

        host = request.get_domain()
        average_rtt, num_samples = self._get_average_rtt(TIMEOUT_ADJUST_LIMIT, host)

        if num_samples < (TIMEOUT_ADJUST_LIMIT / 2):
            msg = (
                "Not enough samples collected (%s) to adjust timeout."
                " Keeping the current value of %s seconds"
            )
            self._log_debug(msg, num_samples, self._get_timeout(host))
        else:
            self._set_timeout(average_rtt * TIMEOUT_MULT_CONST, host)

    def increase_after_error(self, request, exception) -> None:
        host = request.get_domain()
        timeout = self._get_timeout(host) * TIMEOUT_INCREASE_MULT
        msg = "Will increase timeout to %.2f seconds after HTTP socket error (did:%s)"
        self._log_debug(msg, timeout, request.debugging_id)
        self._set_timeout(timeout, host)
