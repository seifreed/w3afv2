"""Apply scan policies before an HTTP request reaches the transport."""

from collections.abc import Callable

from w3af.core.data.fuzzer.utils import rand_alnum


def create_debugging_id() -> str:
    return rand_alnum(8)


class RequestPreflight:
    """Coordinate request policies that must run before sending."""

    def __init__(
        self,
        request_control,
        error_pause_controller,
        rate_limiter,
        timeout_adjustment,
        request_metrics,
        debugging_id_factory: Callable[[], str] = create_debugging_id,
    ) -> None:
        self._request_control = request_control
        self._error_pause_controller = error_pause_controller
        self._rate_limiter = rate_limiter
        self._timeout_adjustment = timeout_adjustment
        self._request_metrics = request_metrics
        self._debugging_id_factory = debugging_id_factory

    def prepare(self, request, exploit_mode: bool) -> None:
        self._request_control.raise_if_should_stop()
        self._request_control.pause_and_stop()
        self._error_pause_controller.pause_on_error(request)

        if not exploit_mode:
            self._rate_limiter.wait()
            self._timeout_adjustment.adjust(request)

        self._request_metrics.increment_requests()

        if request.debugging_id is None:
            request.debugging_id = self._debugging_id_factory()
