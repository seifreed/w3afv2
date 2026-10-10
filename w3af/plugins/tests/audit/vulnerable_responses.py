"""
vulnerable_responses.py

Copyright 2026 w3af contributors

This file is part of w3af, http://w3af.org/ .

w3af is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation version 2 of the License.

w3af is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with w3af; if not, write to the Free Software
Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
"""

import re
import time
import urllib.parse

ETC_USERS_FILE = (
    "root:x:0:0:root:/root:/bin/bash\n"
    "daemon:x:1:1:daemon:/usr/sbin:/bin/sh\n"
    "www-data:x:33:33:www-data:/var/www:/bin/sh\n"
)


def request_params(request):
    """
    :return: A dict with the query string and url-encoded body parameters
             sent in the request, the body values win.
    """
    query = urllib.parse.urlsplit(request.uri).query
    params = urllib.parse.parse_qs(query, keep_blank_values=True)
    body = request.body.decode("utf-8", errors="replace")
    params.update(urllib.parse.parse_qs(body, keep_blank_values=True))
    return {name: values[0] for name, values in params.items()}


def request_param(request, name):
    return request_params(request).get(name, "")


def html_page(response_headers, body, status=200):
    response_headers["Content-Type"] = "text/html"
    return status, response_headers, f"<html><body>{body}</body></html>"


def sleep_for_payload(value, delay_regex):
    """
    Sleep for the amount of seconds captured by delay_regex in value,
    emulating the server side execution of an injected delay.
    """
    match = re.search(delay_regex, value)
    if match is not None:
        time.sleep(float(match.group(1)))
