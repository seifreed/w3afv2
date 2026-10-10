"""Retry failed HTTP requests with refreshed connection settings."""

from w3af.core.data.url.exceptions import HTTPRequestException
from w3af.core.data.url.helpers import get_exception_reason


class RequestRetryHandler:
    """Apply the retry policy for a failed HTTP request."""

    def __init__(self, send, get_timeout, log_debug) -> None:
        self._send = send
        self._get_timeout = get_timeout
        self._log_debug = log_debug

    def retry(self, request, grep, url_error):
        request.retries_left -= 1

        if request.retries_left <= 0:
            error_str = get_exception_reason(url_error) or str(url_error)
            raise HTTPRequestException(error_str, request=request)

        msg = 'Re-sending request "%s" (did:%s) after initial exception: "%s"'
        self._log_debug(msg, request, request.debugging_id, url_error)
        request.set_timeout(self._get_timeout(request.host))
        request.set_new_connection(True)
        return self._send(request, grep=grep)
