"""
test_shells.py

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

import unittest

from w3af.core.controllers.intrusion_tools.exec_method_helpers import os_detection_exec
from w3af.core.controllers.payload_transfer.payload_transfer_factory import (
    payload_transfer_factory,
)
from w3af.core.data.kb.exec_shell import ExecShell as DataExecShell
from w3af.core.data.kb.read_shell import ReadShell as DataReadShell
from w3af.core.data.kb.shell import Shell as DataShell
from w3af.plugins.attack.payloads import payload_handler
from w3af.plugins.attack.payloads.shells import ExecShell, ReadShell, Shell


class TestWiredShells(unittest.TestCase):
    def test_shells_are_data_layer_instances(self):
        # The wired classes remain the KB data types, so the console UI
        # isinstance(x, Shell) checks keep working.
        self.assertTrue(issubclass(Shell, DataShell))
        self.assertTrue(issubclass(ReadShell, DataReadShell))
        self.assertTrue(issubclass(ExecShell, DataExecShell))

    def test_payload_handler_is_injected(self):
        self.assertIs(Shell._payload_handler, payload_handler)
        self.assertIs(ReadShell._payload_handler, payload_handler)
        self.assertIs(ExecShell._payload_handler, payload_handler)

    def test_exec_shell_remote_collaborators_are_injected(self):
        self.assertIs(ExecShell._os_detector, os_detection_exec)
        self.assertIs(ExecShell._payload_transfer_factory, payload_transfer_factory)

    def test_data_layer_shells_have_no_collaborators(self):
        # The data-layer base classes must stay free of the outer-layer
        # collaborators; only the plugins-layer wiring provides them.
        self.assertIsNone(DataShell._payload_handler)
        self.assertIsNone(DataExecShell._os_detector)
        self.assertIsNone(DataExecShell._payload_transfer_factory)


if __name__ == "__main__":
    unittest.main()
