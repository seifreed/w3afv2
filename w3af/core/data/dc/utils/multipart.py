"""
multipart.py

Copyright 2014 Andres Riancho

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

import mimetypes
import os

from w3af.core.data.constants.encodings import DEFAULT_ENCODING
from w3af.core.data.misc.encoding import smart_unicode
from w3af.core.data.misc.io import is_file_like


def encode_as_multipart(multipart_container, boundary):
    """
    Encode the DataContainer using multipart/post , given the provided boundary

    :param multipart_container: The container to encode
    :param boundary: Using this boundary (a random string)
    :return: The post-data that should be sent
    """
    v_vars, v_files = _split_vars_files(multipart_container)
    _, data = multipart_encode(v_vars, v_files, boundary=boundary)
    return data


def _split_vars_files(data):
    """
    Based on the request it decides if we should send the request as
    multipart or not.

    :return: (List with string variables,
              List with file variables)
    """
    v_vars = []
    v_files = []

    for token in data.iter_tokens():

        pname = token.get_name()
        value = token.get_value()

        if is_file_like(value):
            if not value.closed:
                v_files.append((pname, value))
            else:
                v_vars.append((pname, ""))
        else:
            v_vars.append((pname, value))

    return v_vars, v_files


def get_boundary():
    """
    Before I used:
        boundary = mimetools.choose_boundary()

    But that returned some "private" information:
        '127.0.0.1.1000.6267.1173556103.828.1'

    Now I simply return a fixed string which I generated once and now re-use
    all the time.

    There is a reason for having a fixed boundary! When comparing two fuzzable
    requests it's easier to do it if the boundaries are static. This allows
    get_request_hash() to work as expected.

    The problem with fixed boundaries is that they might be used to fingerprint
    w3af, or that they might appear in the data we send to the wire and break
    the request.

    :return:
    """
    return "b08c02-53d780-e2bc43-1d5278-a3c0d9-a5c0d9"


def multipart_encode(_vars, files, boundary=None, _buffer=None):
    if boundary is None:
        boundary = get_boundary()

    if _buffer is None:
        _buffer = ""

    for key, value in _vars:
        key = smart_unicode(key, encoding=DEFAULT_ENCODING, errors="ignore")
        value = smart_unicode(value, encoding=DEFAULT_ENCODING, errors="ignore")
        _buffer += f"--{boundary}\r\n"
        _buffer += f'Content-Disposition: form-data; name="{key}"'
        _buffer += "\r\n\r\n" + value + "\r\n"

    for key, fd in files:
        fd.seek(0)
        filename = fd.name.split(os.path.sep)[-1]

        guessed_mime = mimetypes.guess_type(filename)[0]
        content_type = guessed_mime or "application/octet-stream"
        args = (
            smart_unicode(key, encoding=DEFAULT_ENCODING, errors="ignore"),
            smart_unicode(filename, encoding=DEFAULT_ENCODING, errors="ignore"),
        )

        _buffer += f"--{boundary}\r\n"
        _buffer += (
            'Content-Disposition: form-data; name="{}"; filename="{}"\r\n'.format(*args)
        )
        _buffer += f"Content-Type: {content_type}\r\n"
        content = smart_unicode(fd.read(), encoding=DEFAULT_ENCODING, errors="ignore")
        _buffer += f"\r\n{content}\r\n"

    _buffer += f"--{boundary}--\r\n\r\n"

    return boundary, _buffer
