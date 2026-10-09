"""
http_log.py

Copyright 2006 Andres Riancho

This file is part of w3af, http://w3af.org/ .

w3af is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License version 2 as
published by the Free Software Foundation.

w3af is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with w3af; if not, write to the Free Software
Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
"""

import urllib.request
from collections.abc import Callable

from w3af.core.data.url.HTTPRequest import HTTPRequest
from w3af.core.data.url.HTTPResponse import HTTPResponse


class HTTPLogHandler(urllib.request.BaseHandler):
    handler_order = urllib.request.HTTPErrorProcessor.handler_order - 1

    def __init__(self, log_http: Callable[[HTTPRequest, HTTPResponse], None]):
        self._log_http = log_http

    def http_response(self, request, response):
        self._log_req_resp(request, response)
        return response

    https_response = http_response

    def _log_req_resp(self, request, response):
        if not isinstance(response, HTTPResponse):
            url = request.url_object
            http_response = HTTPResponse.from_httplib_resp(response, original_url=url)
            http_response.set_id(response.id)
        else:
            http_response = response

        if not isinstance(request, HTTPRequest):
            msg = (
                "There is something odd going on in HTTPLogHandler,"
                " request should be of type HTTPRequest got %s"
                " instead."
            )
            raise TypeError(msg % type(request))

        self._log_http(request, http_response)
