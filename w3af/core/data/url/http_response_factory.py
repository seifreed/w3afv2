"""Build HTTP responses from standard-library response objects."""

import urllib.error

from w3af.core.data.dc.headers import Headers
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.url.http_response import (
    DEFAULT_WAIT_TIME,
    merge_repeated_headers,
)


def from_httplib_resp(
    response_class: type,
    httplibresp,
    original_url=None,
    binary_response=False,
    parser_cache=None,
):
    """Create a response model from an ``http.client`` response."""
    code, msg, raw_headers, body = (
        httplibresp.code,
        httplibresp.msg,
        httplibresp.info(),
        httplibresp.read(),
    )
    headers = Headers(merge_repeated_headers(raw_headers.items()))

    if original_url:
        url = URL(httplibresp.geturl(), original_url.encoding).url_decode()
    else:
        url = original_url = URL(httplibresp.geturl())

    response_time = DEFAULT_WAIT_TIME
    if hasattr(httplibresp, "get_wait_time"):
        response_time = httplibresp.get_wait_time()

    if isinstance(httplibresp, urllib.error.HTTPError):
        charset = getattr(httplibresp.fp, "encoding", None)
    else:
        charset = getattr(httplibresp, "encoding", None)

    return response_class(
        code,
        body,
        headers,
        url,
        original_url,
        msg,
        charset=charset,
        time=response_time,
        binary_response=binary_response,
        parser_cache=parser_cache,
    )
