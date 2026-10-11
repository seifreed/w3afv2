"""Open prepared HTTP requests and route transport failures."""

import http.client
import importlib
import urllib.error
from collections.abc import Callable
from http.client import BadStatusLine
from typing import Any, Protocol, cast

from w3af.core.data.url.exceptions import ConnectionPoolException, HTTPRequestException
from w3af.core.data.url.handlers.keepalive import URLTimeoutError

openssl: Any = importlib.import_module("OpenSSL")


class HTTPErrorWithId(Protocol):
    id: int


class IdGenerator(Protocol):
    def inc(self) -> int: ...


class RequestSender:
    """Own the transport boundary for one prepared request."""

    def __init__(
        self,
        before_send: Callable[[Any], None],
        assert_allowed_proto: Callable[[Any], None],
        get_opener: Callable[[], Any],
        apply_evasion: Callable[[Any], Any],
        id_generator: IdGenerator,
        handle_socket_error: Callable[..., Any],
        handle_urllib_error: Callable[..., Any],
        handle_success: Callable[..., Any],
    ) -> None:
        self._before_send = before_send
        self._assert_allowed_proto = assert_allowed_proto
        self._get_opener = get_opener
        self._apply_evasion = apply_evasion
        self._id_generator = id_generator
        self._handle_socket_error = handle_socket_error
        self._handle_urllib_error = handle_urllib_error
        self._handle_success = handle_success

    def send(self, request: Any, grep: bool = True) -> Any:
        """Send a request and dispatch the result to the matching handler."""
        self._before_send(request)
        self._assert_allowed_proto(request)

        original_url = request._original_url
        original_url_inst = request._original_url_object
        request = self._apply_evasion(request)
        request._original_url = original_url
        request._original_url_object = original_url_inst

        try:
            response = self._get_opener().open(request)
        except urllib.error.HTTPError as error:
            http_error = cast(HTTPErrorWithId, error)
            if not hasattr(http_error, "id"):
                http_error.id = self._id_generator.inc()

            return self._handle_success(
                request, error, grep, original_url, original_url_inst
            )
        except (
            OSError,
            URLTimeoutError,
            ConnectionPoolException,
            openssl.SSL.Error,
            openssl.SSL.SysCallError,
            openssl.SSL.ZeroReturnError,
            BadStatusLine,
        ) as error:
            return self._handle_socket_error(request, error, grep, original_url)
        except (http.client.HTTPException, HTTPRequestException) as error:
            return self._handle_urllib_error(request, error, grep, original_url)

        return self._handle_success(
            request, response, grep, original_url, original_url_inst
        )
