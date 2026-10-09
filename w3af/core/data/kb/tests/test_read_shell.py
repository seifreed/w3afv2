"""
test_read_shell.py

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

import shutil
import tempfile
import unittest
from pathlib import Path

from w3af.core.data.constants.severity import INFORMATION
from w3af.core.data.kb.read_shell import ReadShell
from w3af.core.data.kb.tests.local_shells import DirectoryReadShell
from w3af.core.data.kb.tests.test_vuln import MockVuln
from w3af.core.data.kb.vuln import Vuln


class TestReadShell(unittest.TestCase):

    def test_help_format(self):
        shell = ReadShell(MockVuln(), None, None)
        _help = shell.help(None)

        self.assertFalse(_help.startswith(" "))

        self.assertIn("    help", _help)
        # Note that I add an extra space
        self.assertNotIn("     help", _help)

    def test_help_contents(self):
        shell = ReadShell(MockVuln(), None, None)
        _help = shell.help(None)

        self.assertNotIn("execute", _help)
        self.assertNotIn("upload", _help)
        self.assertIn("read", _help)

    def test_help_contents_specific(self):
        shell = ReadShell(MockVuln(), None, None)
        _help = shell.help("read")

        self.assertIn("read", _help)
        self.assertIn("/etc/passwd", _help)

    def test_end_logs_cleanup(self):
        vuln = Vuln("test", "valid description", INFORMATION, [], "test")
        shell = ReadShell(vuln, None, None)

        with self.assertLogs("w3af.core.data.kb.read_shell", level="DEBUG") as logs:
            shell.end()

        self.assertEqual(
            logs.output, ["DEBUG:w3af.core.data.kb.read_shell:Shell cleanup complete."]
        )


class TestDirectoryReadShell(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.directory)
        self.shell = DirectoryReadShell(MockVuln(), self.directory)

    def test_read_is_abstract(self):
        shell = ReadShell(MockVuln(), None, None)

        self.assertRaises(NotImplementedError, shell.read, "/etc/passwd")

    def test_help_download(self):
        self.assertIn("download /etc/passwd /tmp/passwd", self.shell.help("download"))

    def test_identify_linux(self):
        self.shell.add_file("/etc/passwd", "root:x:0:0:root:/root:/bin/bash")

        self.assertEqual(repr(self.shell), '<shell object (rsystem: "linux")>')
        self.assertEqual(self.shell.get_remote_user(), "file-reader")

    def test_identify_unknown(self):
        self.assertEqual(str(self.shell), '<shell object (rsystem: "unknown")>')
        self.assertEqual(self.shell.get_remote_system(), "unknown")

    def test_user_input_read(self):
        self.shell.add_file("/etc/hosts", "127.0.0.1 localhost")

        self.assertEqual(
            self.shell.generic_user_input("read", ["/etc/hosts"]), "127.0.0.1 localhost"
        )
        self.assertIn(
            "Only one parameter is expected",
            self.shell.generic_user_input("read", []),
        )

    def test_user_input_download(self):
        self.shell.add_file("/etc/hosts", "127.0.0.1 localhost")
        local = Path(self.directory, "downloaded")

        self.assertEqual(
            self.shell.generic_user_input("download", ["/etc/hosts", str(local)]),
            "Success.",
        )
        self.assertEqual(local.read_text(), "127.0.0.1 localhost")

    def test_download_errors(self):
        self.shell.add_file("/etc/hosts", "127.0.0.1 localhost")
        invalid_local = str(Path(self.directory, "missing-dir", "hosts"))

        self.assertEqual(
            self.shell.download("/etc/missing", "unused"), "Remote file does not exist."
        )
        self.assertEqual(
            self.shell.download("/etc/hosts", invalid_local),
            "Failed to open local file for writing.",
        )

    def test_user_input_unknown_command(self):
        self.assertEqual(
            self.shell.generic_user_input("ls", []),
            'Command "ls" not found. Please type "help".',
        )
        self.assertIsNone(self.shell.specific_user_input("ls", [], return_err=False))
