"""
sql_identifier.py

Copyright 2024 Andres Riancho

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

_SAFE_SQL_IDENTIFIER = re.compile(r"^[A-Za-z0-9_]+$")


def require_safe_identifier(name):
    """
    SQLite does not allow table or column names to be passed as bound
    parameters, so they must be interpolated into the statement text. This
    guard ensures that only internally generated identifiers (letters, digits
    and underscores) ever reach the SQL string, which makes the absence of an
    injection vector explicit instead of implicit.

    :param name: The table or column identifier to validate.
    :return: The validated identifier.
    """
    if not isinstance(name, str) or not _SAFE_SQL_IDENTIFIER.match(name):
        raise ValueError(f"Unsafe SQL identifier: {name!r}")

    return name
