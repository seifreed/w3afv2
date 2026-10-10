"""Prepare HTTP requests before they reach the opener."""

from w3af.core.data.dc.headers import Headers
from w3af.core.data.url.exceptions import HTTPRequestException
from w3af.core.data.user_agent.random_user_agent import get_random_user_agent


class RequestPreparer:
    """Apply configured headers and validate request protocols."""

    def __init__(self, settings) -> None:
        self._settings = settings

    def add_headers(self, request, headers=None):
        headers = headers or Headers()

        for header_name, header_value in self._settings.header_list:
            request.add_header(header_name, header_value)

        for header_name, header_value in headers.items():
            request.add_header(header_name, header_value)

        if self._settings.rand_user_agent is True:
            request.add_header("User-Agent", get_random_user_agent())

        return request

    def assert_allowed_proto(self, request) -> None:
        full_url = request.get_full_url().lower()

        if not full_url.startswith("http"):
            msg = 'Unsupported URL: "%s"'
            raise HTTPRequestException(msg % request.get_full_url(), request=request)
