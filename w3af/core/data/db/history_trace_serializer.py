"""Serialize and deserialize request/response history traces."""

import msgpack

from w3af.core.data.url.http_request import HTTPRequest
from w3af.core.data.url.http_response import HTTPResponse


class TraceReadException(Exception):
    """Raised when a trace payload cannot be decoded safely."""


class HistoryTraceSerializer:
    """Encode HTTP request/response pairs with a format canary."""

    def __init__(self, canary: str) -> None:
        self._canary = canary

    def serialize(self, request: HTTPRequest, response: HTTPResponse) -> bytes:
        data = (request.to_dict(), response.to_dict(), self._canary)
        return msgpack.dumps(data)

    def deserialize(self, serialized_trace: bytes) -> tuple[HTTPRequest, HTTPResponse]:
        try:
            data = msgpack.loads(serialized_trace, use_list=True)
        except ValueError:
            raise TraceReadException(f"Failed to load {serialized_trace!r}")

        try:
            request_dict, response_dict, canary = data
        except TypeError:
            raise TraceReadException(
                f"Not all components found in {serialized_trace!r}"
            )

        if canary != self._canary:
            raise TraceReadException(f"Invalid canary in {serialized_trace!r}")

        return HTTPRequest.from_dict(request_dict), HTTPResponse.from_dict(
            response_dict
        )
