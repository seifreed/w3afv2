"""Build HTTP requests from the public ExtendedUrllib API."""

from w3af.core.data.dc.headers import Headers
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.url.http_request import HTTPRequest


class RequestBuilder:
    """Validate request inputs and build configured HTTPRequest instances."""

    def __init__(self, get_settings, setup, get_timeout, add_headers):
        self._get_settings = get_settings
        self._setup = setup
        self._get_timeout = get_timeout
        self._add_headers = add_headers

    def build_get(
        self,
        uri,
        data,
        headers,
        cache,
        cookies,
        session,
        error_handling,
        timeout,
        follow_redirects,
        use_basic_auth,
        use_proxy,
        debugging_id,
        new_connection,
        binary_response,
    ):
        headers = headers or Headers()
        self._validate(
            uri,
            headers,
            "The uri parameter of ExtendedUrllib.GET() must be of url.URL type.",
            "The header parameter of ExtendedUrllib.GET() must be of Headers type.",
        )

        return self._build(
            uri,
            data,
            headers,
            cache,
            cookies,
            session,
            error_handling,
            timeout,
            "GET",
            follow_redirects,
            use_basic_auth,
            use_proxy,
            debugging_id,
            new_connection,
            binary_response,
        )

    def build_post(
        self,
        uri,
        data,
        headers,
        cookies,
        session,
        error_handling,
        timeout,
        use_basic_auth,
        use_proxy,
        debugging_id,
        new_connection,
        binary_response,
    ):
        headers = headers or Headers()
        self._validate(
            uri,
            headers,
            "The uri parameter of ExtendedUrllib.POST() must be of url.URL type. "
            f"Got {type(uri)} instead.",
            "The header parameter of ExtendedUrllib.POST() must be of Headers type.",
        )

        if not isinstance(data, (str, bytes)):
            data = str(data)

        return self._build(
            uri,
            data,
            headers,
            False,
            cookies,
            session,
            error_handling,
            timeout,
            "POST",
            False,
            use_basic_auth,
            use_proxy,
            debugging_id,
            new_connection,
            binary_response,
        )

    def build_custom(
        self,
        method,
        uri,
        data,
        headers,
        cache,
        cookies,
        session,
        error_handling,
        timeout,
        use_basic_auth,
        use_proxy,
        follow_redirects,
        debugging_id,
        new_connection,
        binary_response,
    ):
        headers = headers or Headers()
        self._validate(
            uri,
            headers,
            "The uri parameter of any_method must be of url.URL type.",
            "The headers parameter of any_method must be of Headers type.",
        )

        return self._build(
            uri,
            data,
            headers,
            cache,
            cookies,
            session,
            error_handling,
            timeout,
            method,
            follow_redirects,
            use_basic_auth,
            use_proxy,
            debugging_id,
            new_connection,
            binary_response,
        )

    def _validate(self, uri, headers, uri_error, headers_error):
        if not isinstance(uri, URL):
            raise TypeError(uri_error)

        if not isinstance(headers, Headers):
            raise TypeError(headers_error)

    def _build(
        self,
        uri,
        data,
        headers,
        cache,
        cookies,
        session,
        error_handling,
        timeout,
        method,
        follow_redirects,
        use_basic_auth,
        use_proxy,
        debugging_id,
        new_connection,
        binary_response,
    ):
        self._setup()
        timeout = self._resolve_timeout(uri, timeout)
        request = HTTPRequest(
            uri,
            data=data,
            cookies=cookies,
            session=session,
            cache=cache,
            error_handling=error_handling,
            method=method,
            retries=self._get_settings().get_max_retrys(),
            timeout=timeout,
            new_connection=new_connection,
            follow_redirects=follow_redirects,
            use_basic_auth=use_basic_auth,
            use_proxy=use_proxy,
            debugging_id=debugging_id,
            binary_response=binary_response,
        )
        return self._add_headers(request, headers)

    def _resolve_timeout(self, uri, timeout):
        if timeout is not None:
            return timeout

        return self._get_timeout(uri.get_domain())
