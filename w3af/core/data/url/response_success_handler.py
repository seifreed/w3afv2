"""Process successful HTTP responses returned by the opener."""

import urllib.parse

from w3af.core.data.misc.encoding import smart_unicode
from w3af.core.data.url.http_response import HTTPResponse


class ResponseSuccessHandler:
    """Build response objects and publish successful request results."""

    def __init__(
        self,
        log_debug,
        log_successful_response,
        track_rtt,
        adjust_workers,
        grep,
        parser_cache,
    ) -> None:
        self._log_debug = log_debug
        self._log_successful_response = log_successful_response
        self._track_rtt = track_rtt
        self._adjust_workers = adjust_workers
        self._grep = grep
        self._parser_cache = parser_cache

    def handle(self, request, response, grep, original_url, original_url_inst):
        request_data = request.get_data()

        if not request_data:
            method = request.get_method()
            decoded_url = urllib.parse.unquote_plus(original_url)
            msg = f'{method} {decoded_url} returned HTTP code "{response.code}"'
        else:
            printable_data = urllib.parse.unquote_plus(smart_unicode(request_data))
            if len(request_data) > 75:
                printable_data = f"{printable_data[:75]}..."
                printable_data = printable_data.replace("\n", " ")
                printable_data = printable_data.replace("\r", " ")

            msg = (
                f'{request.get_method()} {original_url} with data: "{printable_data}" '
                f'returned HTTP code "{response.code}"'
            )

        from_cache = hasattr(response, "from_cache") and response.from_cache
        http_response = HTTPResponse.from_httplib_resp(
            response,
            original_url=original_url_inst,
            binary_response=request.with_binary_response(),
            parser_cache=self._parser_cache,
        )
        http_response.set_id(response.id)
        http_response.set_from_cache(from_cache)
        http_response.set_debugging_id(request.debugging_id)

        response_info = (
            response.id,
            from_cache,
            grep,
            http_response.get_wait_time(),
            http_response.get_body_length(),
            request.debugging_id,
        )
        msg += (
            f" (id:{response_info[0]}, from_cache:{int(response_info[1])}, "
            f"grep:{int(response_info[2])}, rtt:{response_info[3]:.2f}, "
            f"body:{response_info[4]}, did:{response_info[5]})"
        )
        self._log_debug(msg)

        self._log_successful_response(http_response)
        self._track_rtt(response, request.debugging_id)
        self._adjust_workers()

        if grep:
            self._grep(request, http_response)

        return http_response
