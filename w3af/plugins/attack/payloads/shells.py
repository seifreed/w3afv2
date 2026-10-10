"""
shells.py

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

from functools import partial

from w3af.core.controllers.intrusion_tools.exec_method_helpers import os_detection_exec
from w3af.core.controllers.payload_transfer.payload_transfer_factory import (
    payload_transfer_factory,
)
from w3af.core.data.kb.exec_shell import ExecShell as _ExecShell
from w3af.core.data.kb.read_shell import ReadShell as _ReadShell
from w3af.core.data.kb.shell import Shell as _Shell
from w3af.plugins.attack.payloads import payload_handler


class Shell(_Shell):
    """Data-layer Shell wired with the plugins-layer payload handler."""

    _payload_handler = payload_handler
    _output = None

    def set_output(self, output):
        self._output = output
        self._payload_transfer_factory = partial(
            payload_transfer_factory, output=output
        )


class ReadShell(_ReadShell, Shell):
    """ReadShell able to run payloads through the injected payload handler."""


class ExecShell(_ExecShell, Shell):
    """ExecShell wired with payload, remote OS detection and transfer helpers."""

    _os_detector = staticmethod(os_detection_exec)
    _payload_transfer_factory = staticmethod(payload_transfer_factory)
