"""
utils.py

Copyright 2006 Andres Riancho

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

import sys
from importlib.util import find_spec


def verify_python_version(version_info=sys.version_info):
    """
    Require Python 3.14.
    """
    if version_info[:2] != (3, 14):
        version = ".".join(str(part) for part in version_info[:3])
        print(f"Error: Python 3.14 required; found Python {version}.")
        sys.exit(1)


def verify_pip_available(module_name="pip"):
    if find_spec(module_name) is None:
        print("We recommend you install pip before continuing.")
        print("http://www.pip-installer.org/en/latest/installing.html")
        sys.exit(1)


def running_in_virtualenv():
    return sys.prefix != sys.base_prefix
