"""Expose the public request-building API used by the URL opener."""

from w3af.core.data.parsers.doc.http_request_parser import http_request_parser
from w3af.core.data.url.helpers import get_clean_body


class RequestApi:
    """Build public requests and hand them to the transport callback."""

    def __init__(self, request_builder, size_limit_override, send_request):
        self._request_builder = request_builder
        self._size_limit_override = size_limit_override
        self._send_request = send_request

    def send_clean(self, mutant, debugging_id=None, grep=True):
        http_response = self.send_mutant(
            mutant, cache=False, debugging_id=debugging_id, grep=grep
        )
        return http_response, get_clean_body(mutant, http_response)

    def send_raw_request(self, head, postdata):
        fuzz_req = http_request_parser(head, postdata)
        method = getattr(self, fuzz_req.get_method())
        return method(
            fuzz_req.get_uri(),
            data=fuzz_req.get_data(),
            headers=fuzz_req.get_headers(),
            cache=False,
            grep=False,
        )

    def send_mutant(
        self,
        mutant,
        callback=None,
        grep=True,
        cache=True,
        cookies=True,
        session=None,
        error_handling=True,
        timeout=None,
        follow_redirects=False,
        use_basic_auth=True,
        respect_size_limit=True,
        debugging_id=None,
        binary_response=False,
    ):
        uri = mutant.get_uri()
        data = mutant.get_data()
        headers = mutant.get_all_headers()

        if cookies:
            mutant_cookie = mutant.get_cookie()
            if mutant_cookie:
                headers["Cookie"] = str(mutant_cookie)

        kwargs = {
            "data": data,
            "headers": headers,
            "grep": grep,
            "cache": cache,
            "cookies": cookies,
            "session": session,
            "error_handling": error_handling,
            "timeout": timeout,
            "follow_redirects": follow_redirects,
            "use_basic_auth": use_basic_auth,
            "respect_size_limit": respect_size_limit,
            "debugging_id": debugging_id,
            "binary_response": binary_response,
        }
        method = getattr(self, mutant.get_method())
        response = method(uri, **kwargs)

        if callback is not None:
            callback(mutant, response)

        return response

    def GET(
        self,
        uri,
        data=None,
        headers=None,
        cache=False,
        grep=True,
        cookies=True,
        session=None,
        respect_size_limit=True,
        new_connection=False,
        error_handling=True,
        timeout=None,
        follow_redirects=False,
        use_basic_auth=True,
        use_proxy=True,
        debugging_id=None,
        binary_response=False,
    ):
        request = self._request_builder.build_get(
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
        )

        with self._size_limit_override.apply(respect_size_limit):
            return self._send_request(request, grep=grep)

    def POST(
        self,
        uri,
        data="",
        headers=None,
        grep=True,
        cache=False,
        cookies=True,
        session=None,
        error_handling=True,
        timeout=None,
        follow_redirects=None,
        use_basic_auth=True,
        use_proxy=True,
        debugging_id=None,
        new_connection=False,
        respect_size_limit=None,
        binary_response=False,
    ):
        request = self._request_builder.build_post(
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
        )

        return self._send_request(request, grep=grep)

    def __getattr__(self, method_name):
        def any_method(
            uri,
            data=None,
            headers=None,
            cache=False,
            grep=True,
            cookies=True,
            session=None,
            error_handling=True,
            timeout=None,
            use_basic_auth=True,
            use_proxy=True,
            follow_redirects=False,
            debugging_id=None,
            new_connection=False,
            respect_size_limit=None,
            binary_response=False,
        ):
            request = self._request_builder.build_custom(
                method_name,
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
            )
            return self._send_request(request, grep=grep)

        any_method.__doc__ = f"Send {method_name} HTTP request"
        return any_method
