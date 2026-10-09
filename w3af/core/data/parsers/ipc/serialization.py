"""
serialization.py

Copyright 2018 Andres Riancho

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

import contextlib
import os
import tempfile

import msgpack

from w3af.core.data.misc import serialize
from w3af.core.data.parsers.doc.sgml import Tag
from w3af.core.filesystem import create_temp_dir, get_temp_dir

DESERIALIZATION_ERRORS = (
    OSError,
    EOFError,
    ValueError,
    KeyError,
    TypeError,
    serialize.UnpicklingError,
)


class DeserializationError(Exception):
    """Raised when a temp file written by another process can not be loaded."""


def write_http_response_to_temp_file(http_response):
    """
    Write an HTTPResponse instance to a temp file using msgpack

    :param http_response: The HTTP response
    :return: The name of the file
    """
    with get_temp_file("http") as temp:
        msgpack.dump(http_response.to_dict(), temp, use_bin_type=True)
    return temp.name


def load_http_response_from_temp_file(filename, remove=True):
    """
    :param filename: The filename that holds the HTTP response as msgpack
    :param remove: Remove the file after reading
    :return: An HTTP response instance
    """
    # Importing here to prevent import cycle
    from w3af.core.data.url.http_response import HTTPResponse

    return _load_from_temp_file(
        filename,
        remove,
        lambda f: HTTPResponse.from_dict(msgpack.load(f, raw=False)),
    )


def write_tags_to_temp_file(tag_list):
    """
    Write an Tag list to a temp file using msgpack

    :param tag_list: The Tag list
    :return: The name of the file
    """
    with get_temp_file("tags") as temp:
        msgpack.dump([t.to_dict() for t in tag_list], temp, use_bin_type=True)
    return temp.name


def load_tags_from_temp_file(filename, remove=True):
    """
    :param filename: The filename that holds the Tags as msgpack
    :param remove: Remove the file after reading
    :return: A list containing tags
    """
    return _load_from_temp_file(
        filename,
        remove,
        lambda f: [Tag.from_dict(t) for t in msgpack.load(f, raw=False)],
    )


def get_temp_file(_type):
    """
    :return: A named temporary file which will not be removed on close
    """
    create_temp_dir()
    return tempfile.NamedTemporaryFile(
        prefix=f"w3af-{_type}-",
        suffix=".pebble",
        delete=False,
        dir=get_temp_dir(),
    )


def write_object_to_temp_file(obj):
    """
    Write an object to a temp file using cPickle to serialize

    :param obj: The object
    :return: The name of the file
    """
    with get_temp_file("parser") as temp:
        serialize.dump(obj, temp, serialize.HIGHEST_PROTOCOL)
    return temp.name


def load_object_from_temp_file(filename, remove=True):
    """
    Load an object from a temp file

    :param filename: The filename where the cPickle serialized object lives
    :param remove: Remove the file after reading
    :return: The object instance
    """
    return _load_from_temp_file(filename, remove, serialize.load)


def _load_from_temp_file(filename, remove, loader):
    """
    Deserialize the content of `filename` with `loader`, optionally removing
    the file afterwards even when deserialization fails.
    """
    try:
        with open(filename, "rb") as serialized:
            return loader(serialized)
    except DESERIALIZATION_ERRORS as error:
        msg = f'Failed to deserialize sub-process result. Exception: "{error}"'
        raise DeserializationError(msg) from error
    finally:
        if remove:
            remove_file_if_exists(filename)


def remove_file_if_exists(filename):
    """
    Remove the file if it exists

    :param filename: The file to remove
    :return: None
    """
    with contextlib.suppress(OSError):
        os.remove(filename)
