"""
ubuntu1204.py

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

from typing import ClassVar

from w3af.core.controllers.misc.external_process import run_process

from ..requirements import CORE
from .base_platform import Platform
from .system_info import distribution_matches


class Ubuntu1204(Platform):
    SYSTEM_NAME = "Ubuntu 12.04"
    PKG_MANAGER_CMD = "sudo apt-get -y install"
    PIP_CMD = "pip"

    CORE_SYSTEM_PACKAGES: ClassVar[list[str]] = [
        "python-pip",
        "npm",
        "python2.7-dev",
        "python-setuptools",
        "build-essential",
        "libsqlite3-dev",
        "libssl-dev",
        "git",
        "libxml2-dev",
        "libxslt1-dev",
        "libyaml-dev",
        "libffi-dev",
    ]

    SYSTEM_PACKAGES: ClassVar[dict[int, list[str]]] = {CORE: CORE_SYSTEM_PACKAGES}

    @staticmethod
    def os_package_is_installed(package_name):
        not_installed = "is not installed and no info is available"

        # The hold string was added after a failed build of w3af-module
        installed = "Status: install ok installed"
        hold = "Status: hold ok installed"

        try:
            result = run_process(["dpkg", "-s", package_name])
        except OSError:
            # We're not on a debian based system
            return None
        else:
            dpkg_output = result.stdout

            if not_installed in dpkg_output:
                return False
            elif installed in dpkg_output or hold in dpkg_output:
                return True
            else:
                return None

    @staticmethod
    def is_current_platform():
        return distribution_matches("ubuntu", "12.04")
