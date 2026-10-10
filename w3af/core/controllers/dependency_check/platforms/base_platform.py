"""
platform.py

Copyright 2014 Andres Riancho

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

from w3af.core.controllers.dependency_check.pip_dependency import PIPDependency

from ..external.retirejs import RETIREJS_COMMAND, retirejs_is_installed
from ..requirements import CORE, CORE_PIP_PACKAGES

RETIREJS_INSTALL_COMMANDS = ["npm install -g retire@2.0.3", "npm update -g retire"]


class Platform:
    """
    Simple base class for defining platforms/operating systems for dependency
    checks.
    """

    PIP_PACKAGES: ClassVar[dict[int, list[PIPDependency]]] = {CORE: CORE_PIP_PACKAGES}

    SYSTEM_PACKAGES: ClassVar[dict[int, list[str]]] = {CORE: []}

    @staticmethod
    def is_current_platform():
        raise NotImplementedError

    @staticmethod
    def os_package_is_installed(package_name):
        raise NotImplementedError

    @staticmethod
    def after_hook():
        pass

    @staticmethod
    def get_missing_external_commands(retirejs_command=RETIREJS_COMMAND):
        if retirejs_is_installed(retirejs_command):
            return []

        return list(RETIREJS_INSTALL_COMMANDS)
