"""
profiling_output.py

Copyright 2026 Andres Riancho

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
import glob
import json
import os


@contextlib.contextmanager
def environment_variables(**variables):
    """
    Set real environment variables for the duration of the block and restore
    the previous state afterwards.
    """
    previous = {name: os.environ.get(name) for name in variables}
    os.environ.update(variables)

    try:
        yield
    finally:
        for name, value in previous.items():
            if value is None:
                del os.environ[name]
            else:
                os.environ[name] = value


def output_files(output_fmt):
    """
    :return: The files this process wrote using the profiling output format
    """
    return sorted(glob.glob(output_fmt % (os.getpid(), "*")))


def remove_output_files(output_fmt):
    for output_file in output_files(output_fmt):
        os.remove(output_file)


def latest_output_file(output_fmt):
    return max(output_files(output_fmt), key=os.path.getmtime)


def read_json_output(output_fmt):
    """
    :return: The decoded content of the latest file written with output_fmt
    """
    with open(latest_output_file(output_fmt)) as output_fh:
        return json.load(output_fh)
