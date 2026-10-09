"""
Logging decorators for knowledge-base shell operations.

Copyright 2009-2010 Andres Riancho

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

import logging
from functools import wraps

LOGGER = logging.getLogger(__name__)


def download_debug(fn):
    @wraps(fn)
    def wrapper(self, remote_filename, local_filename):
        result = fn(self, remote_filename, local_filename)
        LOGGER.debug(
            'download( "%s" , "%s") == %s',
            remote_filename,
            local_filename,
            result,
        )
        return result

    return wrapper


def read_debug(fn):
    @wraps(fn)
    def wrapper(self, filename):
        result = fn(self, filename)
        normalized_result = result.replace("\n", "").replace("\r", "")
        preview = normalized_result[:25]
        if len(normalized_result) > 25:
            preview += "..."
        file_content = f'"{preview}"'
        LOGGER.debug(
            'read( "%s" , %s) == %s bytes.', filename, file_content, len(file_content)
        )
        return result

    return wrapper
