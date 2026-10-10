"""Check whether a target server remains reachable after request failures."""

from w3af.core.data.url.exceptions import HTTPRequestException
from w3af.core.data.url.http_request import HTTPRequest
from w3af.core.exceptions import BaseFrameworkException, ScanMustStopException


class ServerReachabilityChecker:
    """Probe the target root URL using a defensive timeout."""

    def __init__(self, get_timeout, set_timeout, add_headers, send, log_debug) -> None:
        self._get_timeout = get_timeout
        self._set_timeout = set_timeout
        self._add_headers = add_headers
        self._send = send
        self._log_debug = log_debug

    def check(self, request) -> bool:
        uri = request.get_uri()
        root_url = uri.base_url()
        host = uri.get_domain()
        timeout = self._get_timeout(host) * 4
        self._set_timeout(timeout, host)

        probe = HTTPRequest(
            root_url,
            cookies=True,
            cache=False,
            error_handling=False,
            method="GET",
            retries=0,
            timeout=timeout,
        )
        probe = self._add_headers(probe)

        try:
            self._send(probe, grep=False)
        except HTTPRequestException as error:
            self._log_debug(
                'Remote URL %s is UNREACHABLE due to: "%s"', root_url, error
            )
            return False
        except (BaseFrameworkException, ScanMustStopException, OSError) as error:
            self._log_debug(
                'Internal error makes URL %s UNREACHABLE due to: "%s"',
                root_url,
                error,
            )
            return False

        self._log_debug("Remote URL %s is reachable", root_url)
        return True
