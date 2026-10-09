"""
auth.py

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

from collections.abc import Callable
from functools import wraps
from hashlib import sha512
from hmac import compare_digest

from flask import request

from w3af.core.ui.api import app
from w3af.core.ui.api.utils.error import abort


def check_auth(username: str | None, password: str | None) -> bool:
    """
    :return: True if the username / password combination is valid
    """
    if username is None or password is None:
        return False

    password_hash = sha512(password.encode("utf-8")).hexdigest()
    valid_username = compare_digest(
        username.encode("utf-8"), str(app.config["USERNAME"]).encode("utf-8")
    )
    valid_password = compare_digest(
        password_hash.encode("utf-8"), str(app.config["PASSWORD"]).encode("utf-8")
    )
    return valid_username and valid_password


def requires_auth[**P, R](f: Callable[P, R]) -> Callable[P, R]:
    @wraps(f)
    def decorated(*args: P.args, **kwargs: P.kwargs) -> R:
        if "PASSWORD" not in app.config:
            # Auth was not enabled at startup
            return f(*args, **kwargs)

        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            abort(
                401,
                "Could not verify access. Please specify a username and"
                " password for HTTP basic authentication.",
            )
        return f(*args, **kwargs)

    return decorated
