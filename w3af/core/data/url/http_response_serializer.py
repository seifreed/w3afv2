"""Serialize and restore HTTP responses for inter-process transport."""

from typing import Any

from w3af.core.data.dc.headers import Headers
from w3af.core.data.parsers.doc.url import URL


def to_dict(response) -> dict[str, Any]:
    """Return the msgpack-compatible representation of a response."""
    return {
        "headers": dict(response.get_headers()),
        "code": response.get_code(),
        "msg": response.get_msg(),
        "body": response.get_body(),
        "time": response.get_wait_time(),
        "id": response.get_id(),
        "charset": response.get_charset(),
        "uri": response.get_uri().url_string,
        "debugging_id": response.get_debugging_id(),
    }


def from_dict(response_class: type, serialized: dict[str, Any]):
    """Restore a response using the supplied response class."""
    uri = URL(serialized["uri"])
    return response_class(
        serialized["code"],
        serialized["body"],
        Headers(list(serialized["headers"].items())),
        uri,
        uri,
        msg=serialized["msg"],
        _id=serialized["id"],
        time=serialized["time"],
        charset=serialized["charset"],
        set_body=True,
        debugging_id=serialized["debugging_id"],
    )
