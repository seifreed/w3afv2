"""
io.py

Copyright 2011 Andres Riancho

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

from io import StringIO


class NamedStringIO(str):
    """
    A file-like string.
    """

    def __new__(cls, the_str, name):
        return super().__new__(cls, the_str)

    def __init__(self, the_str, name):
        self._stream = StringIO(the_str)
        self._name = name

    @property
    def name(self):
        return self._name

    @property
    def closed(self):
        return self._stream.closed

    def read(self, size=-1):
        return self._stream.read(size)

    def write(self, value):
        return self._stream.write(value)

    def seek(self, offset, whence=0):
        return self._stream.seek(offset, whence)


FILE_ATTRS = ("read", "write", "name", "seek", "closed")


def is_file_like(f):
    return all(hasattr(f, at) for at in FILE_ATTRS)
