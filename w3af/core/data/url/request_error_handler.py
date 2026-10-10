"""Handle errors raised while sending HTTP requests."""

from w3af.core.data.url.exceptions import HTTPRequestException
from w3af.core.data.url.helpers import get_exception_reason


class RequestErrorHandler:
    """Apply the error-handling, stop, and retry policy for requests."""

    def __init__(
        self,
        log_debug,
        increase_timeout,
        count_lock,
        log_failed_response,
        should_stop_scan,
        handle_error_count_exceeded,
        adjust_workers,
        retry,
    ) -> None:
        self._log_debug = log_debug
        self._increase_timeout = increase_timeout
        self._count_lock = count_lock
        self._log_failed_response = log_failed_response
        self._should_stop_scan = should_stop_scan
        self._handle_error_count_exceeded = handle_error_count_exceeded
        self._adjust_workers = adjust_workers
        self._retry = retry

    def handle_socket_error(self, request, exception, grep, original_url):
        self._increase_timeout(request, exception)
        return self._handle_generic_error(request, exception, grep, original_url)

    def handle_urllib_error(self, request, exception, grep, original_url):
        return self._handle_generic_error(request, exception, grep, original_url)

    def _handle_generic_error(self, request, exception, grep, original_url):
        if not request.error_handling:
            msg = (
                'Raising HTTP error "%s" "%s" failed reason: "%s". '
                "Error handling was disabled for this request (did:%s)."
            )
            self._log_debug(
                msg,
                request.get_method(),
                original_url,
                exception,
                request.debugging_id,
            )
            error_str = get_exception_reason(exception) or str(exception)
            raise HTTPRequestException(error_str, request=request)

        with self._count_lock:
            self._log_failed_response(request, exception, original_url)
            if self._should_stop_scan(request):
                self._handle_error_count_exceeded(exception)

        self._adjust_workers()
        request._original_url = original_url
        return self._retry(request, grep, exception)
