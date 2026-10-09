"""
suse.py

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


class SuSE(Platform):
    SYSTEM_NAME = "SuSE"
    PKG_MANAGER_CMD = "sudo zypper install"
    PIP_CMD = "pip-2.7"

    CORE_SYSTEM_PACKAGES: ClassVar[list[str]] = [
        "python-pip",
        "npm",
        "python-devel",
        "sqlite3-devel",
        "git",
        "libxml2-devel",
        "libxslt-devel",
        "libffi-devel",
    ]

    SYSTEM_PACKAGES: ClassVar[dict[int, list[str]]] = {CORE: CORE_SYSTEM_PACKAGES}

    @staticmethod
    def os_package_is_installed(package_name):
        not_installed = "is not installed"

        try:
            result = run_process(["rpm", "-q", package_name])
        except OSError:
            # We're not on a suse based system
            return None
        else:
            rpm_output = result.stdout

            if not_installed in rpm_output:
                return False
            elif package_name in rpm_output:
                return True
            else:
                return None

    @staticmethod
    def is_current_platform():
        return distribution_matches("suse")
