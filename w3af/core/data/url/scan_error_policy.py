"""Apply scan-wide policies after repeated HTTP errors."""

from typing import NoReturn

from w3af.core.data.url.constants import MAX_ERROR_COUNT
from w3af.core.data.url.helpers import get_exception_reason
from w3af.core.data.url.response_history import ResponseHistory
from w3af.core.data.url.scan_request_control import ScanRequestControl
from w3af.core.data.url.server_reachability_checker import ServerReachabilityChecker
from w3af.core.exceptions import (
    ScanMustStopByKnownReasonExc,
    ScanMustStopByUnknownReasonExc,
    ScanMustStopException,
)


class ScanErrorPolicy:
    """Decide when repeated request errors must stop a scan."""

    def __init__(
        self,
        response_history: ResponseHistory,
        reachability_checker: ServerReachabilityChecker,
        request_control: ScanRequestControl,
        log_debug,
    ) -> None:
        self._response_history = response_history
        self._reachability_checker = reachability_checker
        self._request_control = request_control
        self._log_debug = log_debug

    def should_stop_scan(self, request) -> bool:
        return self._response_history.should_stop_scan(
            lambda: self.server_root_path_is_reachable(request)
        )

    def server_root_path_is_reachable(self, request) -> bool:
        return self._reachability_checker.check(request)

    def get_error_rate(self) -> int:
        return self._response_history.get_error_rate()

    def log_error_rate(self) -> None:
        error_rate = self.get_error_rate()
        self._log_debug(f"ExtendedUrllib error rate is at {int(error_rate)}%")

    def handle_error_count_exceeded(self, error) -> NoReturn:
        message = (
            "w3af found too many consecutive errors while performing"
            " HTTP requests. In most cases this means that the remote web"
            " server is not reachable anymore, the network is down, or"
            " a WAF is blocking our tests. The last exception message"
            ' was "%s" (%s.%s).'
        )

        reason = get_exception_reason(error)
        error_details = (error, error.__class__.__module__, error.__class__.__name__)
        stop_exception = self._build_stop_exception(message, error_details, reason)

        self._log_debug(
            "The extended urllib will raise a scan must stop exception"
            " for each request after this message. The remote server is"
            " unreachable."
        )
        self._request_control.stop_exception = stop_exception
        raise stop_exception

    def _build_stop_exception(
        self,
        message: str,
        error_details: tuple[object, str, str],
        reason,
    ) -> ScanMustStopException:
        if reason is not None:
            return ScanMustStopByKnownReasonExc(message % error_details, reason=reason)

        recent_errors = self._response_history.get_recent_messages(MAX_ERROR_COUNT)
        return ScanMustStopByUnknownReasonExc(
            message % error_details,
            errs=recent_errors,
        )
