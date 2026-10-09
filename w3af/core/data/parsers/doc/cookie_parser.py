# -*- coding: UTF-8 -*-
"""
cookie_parser.py

Copyright 2015 Andres Riancho

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

import http.cookies

COOKIE_HEADERS = ("set-cookie", "cookie", "cookie2")


def parse_cookie(cookie_header_value):
    """
    Parses the value of a "Set-Cookie" header into a Cookie.SimpleCookie object

    :param cookie_header_value: The value of the "Set-Cookie" header
    :return: A Cookie.SimpleCookie instance.
    :raises http.cookies.CookieError: If the cookie value is not in valid format
    """
    cookie_object = http.cookies.SimpleCookie()
    cookie_object.load(cookie_header_value)

    # Python 3's SimpleCookie silently ignores the cookies it can not parse
    # instead of raising, so a non-empty header that yields no cookie at all
    # is reported as an invalid cookie.
    if cookie_header_value.strip() and not cookie_object:
        msg = f"Invalid cookie value: {cookie_header_value!r}"
        raise http.cookies.CookieError(msg)

    return cookie_object
