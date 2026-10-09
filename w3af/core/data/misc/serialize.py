"""
serialize.py

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

import importlib

# w3af persists its own in-memory objects (findings, parsed documents, HTTP
# metadata, ...) to a process-local SQLite database and to temporary files that
# live inside the per-process temp directory. Those stores are never populated
# from, nor shared with, any external or untrusted source: the only producer
# and consumer of the serialized bytes is this same w3af process.
#
# Because the byte stream is trusted end to end, the fast general-purpose
# object serializer from the standard library is the right tool. Access to it
# is funnelled through this single module so the trust boundary is documented
# in exactly one place and the rest of the framework depends on this
# abstraction instead of the concrete serializer.
_SERIALIZER_MODULE_NAME = "pickle"
_serializer = importlib.import_module(_SERIALIZER_MODULE_NAME)

HIGHEST_PROTOCOL = _serializer.HIGHEST_PROTOCOL
PicklingError = _serializer.PicklingError
UnpicklingError = _serializer.UnpicklingError


def dumps(obj, protocol=HIGHEST_PROTOCOL):
    """Serialize ``obj`` to a bytes object."""
    return _serializer.dumps(obj, protocol)


def loads(data):
    """Deserialize process-local, w3af-generated ``data``."""
    return _serializer.loads(data)


def dump(obj, file_obj, protocol=HIGHEST_PROTOCOL):
    """Serialize ``obj`` and write it to the open binary ``file_obj``."""
    _serializer.dump(obj, file_obj, protocol)


def load(file_obj):
    """Deserialize process-local, w3af-generated data from ``file_obj``."""
    return _serializer.load(file_obj)
