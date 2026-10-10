"""
retirejs.py

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

from w3af.core.controllers.misc.external_process import run_process

SUPPORTED_RETIREJS = "2."
RETIREJS_COMMAND = ("retire",)


def is_supported_version(version):
    """
    :param version: The output of retire --version
    :return: True if it has the format 2.6.0, a version we support.
    """
    version = version.strip()

    # Just check that the version has the format 1.6.0
    if len(version.split(".")) != 3:
        return False

    return version.startswith(SUPPORTED_RETIREJS)


def retirejs_is_installed(command=RETIREJS_COMMAND):
    """
    :param command: The program (and arguments) that run retirejs
    :return: True if retirejs is installed and we were able to parse the version.
    """
    try:
        result = run_process([*command, "--version"])
    except OSError:
        return False

    if result.returncode != 0:
        return False

    return is_supported_version(result.stdout)
