"""
error.py

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

import json
from typing import Any, NoReturn

from werkzeug.exceptions import HTTPException

UNAUTHORIZED = 401
BASIC_AUTH_CHALLENGE = ("WWW-Authenticate", 'Basic realm="w3af", charset="UTF-8"')


class JSONHTTPException(HTTPException):
    def __init__(self, description: str | None = None, code: int | None = None):
        Exception.__init__(self)
        self.response = None
        self.description = description
        self.code = code

    def get_body(self, environ: Any = None, scope: Any = None) -> str:
        """Get the JSON body"""
        return json.dumps({"message": self.description, "code": self.code})

    def get_headers(
        self, environ: Any = None, scope: Any = None
    ) -> list[tuple[str, str]]:
        """
        Get a list of headers, asking browsers for credentials when the request
        was not authenticated.
        """
        headers = [("Content-Type", "application/json")]
        if self.code == UNAUTHORIZED:
            headers.append(BASIC_AUTH_CHALLENGE)
        return headers


def abort(code: int, message: str) -> NoReturn:
    """
    Raise an exception to stop HTTP processing execution

    :param code: 403, 500, etc.
    :param message: A message to show to the user
    :return: None, an exception is raised
    """
    raise JSONHTTPException(message, code)
