"""
test_exec_shell.py

Copyright 2012 Andres Riancho

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

from w3af.core.data.kb.exec_shell import NO_TRANSFER_HANDLER_MSG, ExecShell
from w3af.core.data.kb.shell import NO_PAYLOAD_HANDLER_MSG
from w3af.core.data.kb.tests.test_vuln import MockVuln


class TestExecShell(unittest.TestCase):

    def test_help_format(self):
        shell = ExecShell(MockVuln(), None, None)
        _help = shell.help(None)

        self.assertFalse(_help.startswith(" "))

        self.assertIn("    help", _help)
        # Note that I add an extra space
        self.assertNotIn("     help", _help)

    def test_without_injected_collaborators(self):
        shell = ExecShell(MockVuln(), None, None)

        # No payload handler and no payload transfer factory are injected in the
        # data layer, so the shell degrades gracefully instead of importing the
        # outer layers.
        self.assertEqual(shell._print_runnable_payloads(), NO_PAYLOAD_HANDLER_MSG)
        self.assertEqual(shell.write("/tmp/x", "data"), NO_TRANSFER_HANDLER_MSG)

        shell.identify_os()
        self.assertIsNone(shell.get_remote_os())
        self.assertEqual(shell.get_remote_user(), "unknown")

    def test_help_contents(self):
        shell = ExecShell(MockVuln(), None, None)
        _help = shell.help(None)

        self.assertIn("execute", _help)
        self.assertIn("upload", _help)
