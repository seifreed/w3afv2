"""
fedora.py

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

from ..requirements import CORE
from .base_platform import Platform
from .package_query import query_package
from .system_info import distribution_matches

NOT_INSTALLED = "is not installed"


def classify_rpm_output(output, package_name):
    if NOT_INSTALLED in output:
        return False

    if package_name in output:
        return True

    return None


class Fedora(Platform):
    SYSTEM_NAME = "fedora"
    PKG_MANAGER_CMD = "sudo dnf install"
    PIP_CMD = "python3 -m pip"

    CORE_SYSTEM_PACKAGES: ClassVar[list[str]] = [
        "python3-pip",
        "npm",
        "python3-devel",
        "python3-setuptools",
        "sqlite-devel",
        "git",
        "libxml2-devel",
        "gcc-c++",
        "libxslt-devel",
        "openssl-devel",
        "libffi-devel",
    ]

    SYSTEM_PACKAGES: ClassVar[dict[int, list[str]]] = {CORE: CORE_SYSTEM_PACKAGES}

    @staticmethod
    def os_package_is_installed(package_name):
        return query_package(("rpm", "-q"), package_name, classify_rpm_output)

    @staticmethod
    def is_current_platform():
        return distribution_matches("fedora")
