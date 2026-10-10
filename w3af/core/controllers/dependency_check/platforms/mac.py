"""
mac.py

Copyright 2013 Andres Riancho

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
from typing import ClassVar

from w3af.core.controllers.dependency_check.pip_dependency import PIPDependency
from w3af.core.controllers.dependency_check.platforms.base_platform import Platform
from w3af.core.controllers.dependency_check.platforms.package_query import (
    query_package,
)
from w3af.core.controllers.dependency_check.requirements import (
    CORE,
    CORE_PIP_PACKAGES,
)

TWO_PYTHON_MSG = """\
It seems that your system has two different python installations: One provided
by the operating system, at %s, and another which you installed using Mac ports.

The default Python executable for your system is the one provided by Apple,
and Python 3.14 from MacPorts is required by w3af.

In order to have a working w3af installation you will have to switch to the Mac
ports Python by using the following command:
    sudo port select --set python python314
"""

MACPORTS_PREFIX = "/opt/"
NOT_INSTALLED = "None of the specified ports are installed"
INSTALLED = "The following ports are currently installed"


def classify_port_output(output, package_name):
    if NOT_INSTALLED in output:
        return False

    if INSTALLED in output:
        return True

    return None


def two_python_warning(executable):
    """
    :return: A message for the user when the python executable is not the one
             provided by MacPorts (which keeps the dependencies installed
             under /opt/local), None otherwise.
    """
    if executable.startswith(MACPORTS_PREFIX):
        return None

    return TWO_PYTHON_MSG % executable


class MacOSX(Platform):
    SYSTEM_NAME = "Mac OS X"
    PKG_MANAGER_CMD = "sudo port install"
    PIP_CMD = "python3.14 -m pip"

    #
    # Remember to use http://www.macports.org/ports.php to search for
    # packages
    #
    # Python port includes the dev headers
    CORE_SYSTEM_PACKAGES: ClassVar[list[str]] = [
        "py314-pip",
        "python314",
        "autoconf",
        "automake",
        "git-core",
        "libffi",
    ]

    SYSTEM_PACKAGES: ClassVar[dict[int, list[str]]] = {CORE: CORE_SYSTEM_PACKAGES}

    MAC_CORE_PIP_PACKAGES = CORE_PIP_PACKAGES[:]

    PIP_PACKAGES: ClassVar[dict[int, list[PIPDependency]]] = {
        CORE: MAC_CORE_PIP_PACKAGES
    }

    @staticmethod
    def is_current_platform():
        return sys.platform == "darwin"

    @staticmethod
    def os_package_is_installed(package_name):
        return query_package(
            ("port", "-v", "installed"), package_name, classify_port_output
        )

    @staticmethod
    def after_hook():
        # Is the default python executable the one in macports?
        #
        # We need to warn the user about this situation and let him know how to
        # fix. See: http://stackoverflow.com/questions/118813/
        warning = two_python_warning(sys.executable)
        if warning:
            print(warning)
