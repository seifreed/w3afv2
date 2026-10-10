"""Record failed HTTP responses and their diagnostics."""

import socket
import traceback
from http.client import BadStatusLine

import OpenSSL

from w3af.core.data.misc.encoding import smart_unicode
from w3af.core.data.url.exceptions import ConnectionPoolException
from w3af.core.data.url.handlers.keepalive import URLTimeoutError
from w3af.core.data.url.helpers import get_exception_reason


class FailedResponseRecorder:
    """Persist failure metadata and log diagnostics for a request."""

    def __init__(self, response_history, get_timeout, log_error_rate, log_debug):
        self._response_history = response_history
        self._get_timeout = get_timeout
        self._log_error_rate = log_error_rate
        self._log_debug = log_debug

    def record(self, request, exception, original_url) -> None:
        self._log_debug(
            'Failed to HTTP "%s" "%s". Reason: "%s", going to retry (did:%s)',
            request.get_method(),
            smart_unicode(original_url),
            exception,
            request.debugging_id,
        )

        no_traceback_for = (
            URLTimeoutError,
            ConnectionPoolException,
            BadStatusLine,
            socket.error,
            OpenSSL.SSL.SysCallError,
            OpenSSL.SSL.ZeroReturnError,
        )
        if not isinstance(exception, no_traceback_for):
            self._log_debug("Traceback for this error: %s", traceback.format_exc())

        reason = get_exception_reason(exception) or str(exception)
        host = request.get_domain()
        self._response_history.record_failure(reason, host, self._get_timeout(host))
        self._log_error_rate()
