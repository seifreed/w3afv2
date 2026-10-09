"""
openbsd.py

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

import platform
from typing import ClassVar

from w3af.core.controllers.misc.external_process import run_process

from ..requirements import CORE
from .base_platform import Platform


class OpenBSD5(Platform):
    SYSTEM_NAME = "OpenBSD 5"
    PKG_MANAGER_CMD = "pkg_add -i -v"
    PIP_CMD = "pip-2.7"

    #
    #    Package list here http://ftp.openbsd.org/pub/OpenBSD/5.2/packages/i386/
    #
    CORE_SYSTEM_PACKAGES: ClassVar[list[str]] = [
        "py-pip",
        "python-2.7.3p0",
        "py-setuptools",
        "gcc",
        "git",
        "libxml",
        "libxslt",
        "py-pcapy",
        "py-libdnet",
        "libffi",
    ]

    SYSTEM_PACKAGES: ClassVar[dict[int, list[str]]] = {CORE: CORE_SYSTEM_PACKAGES}

    @staticmethod
    def os_package_is_installed(package_name):
        try:
            result = run_process(["pkg_info"])
        except OSError:
            # We're not on an openbsd based system
            return None

        if result.returncode != 0:
            return None

        pkg_info_output = result.stdout
        return any(
            line.startswith(package_name) for line in pkg_info_output.splitlines()
        )

    @staticmethod
    def after_hook():
        msg = (
            "Before running pkg_add remember to specify the package path using:\n"
            "    export PKG_PATH=ftp://ftp.openbsd.org/pub/OpenBSD/`uname"
            " -r`/packages/`machine -a`/"
        )
        print(msg)

    @staticmethod
    def is_current_platform():
        return "openbsd" in platform.system().lower()
