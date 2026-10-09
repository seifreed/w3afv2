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

import getpass
import shutil
import tempfile
import unittest
from pathlib import Path

from w3af.core.data.kb.exec_shell import NO_TRANSFER_HANDLER_MSG, ExecShell
from w3af.core.data.kb.shell import NO_PAYLOAD_HANDLER_MSG
from w3af.core.data.kb.tests.local_shells import (
    DirectoryTransferHandler,
    LinuxExecShell,
    LocalExecShell,
    TransferFactory,
    WindowsExecShell,
)
from w3af.core.data.kb.tests.test_vuln import MockVuln


class TestExecShell(unittest.TestCase):

    def setUp(self):
        self.directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.directory)
        self.shell = LocalExecShell(MockVuln(), None, None)

    def test_help_format(self):
        _help = self.shell.help(None)

        self.assertFalse(_help.startswith(" "))

        self.assertIn("    help", _help)
        # Note that I add an extra space
        self.assertNotIn("     help", _help)

    def test_help_contents(self):
        _help = self.shell.help(None)

        self.assertIn("execute", _help)
        self.assertIn("upload", _help)

    def test_help_specific_commands(self):
        self.assertIn("read /etc/passwd", self.shell.help("read"))
        self.assertIn("download /etc/passwd /tmp/passwd", self.shell.help("download"))

    def test_execute_is_abstract(self):
        shell = ExecShell(MockVuln(), None, None)

        self.assertRaises(NotImplementedError, shell.execute, "id")

    def test_without_injected_collaborators(self):
        # No payload handler and no payload transfer factory are injected in the
        # data layer, so the shell degrades gracefully instead of importing the
        # outer layers.
        self.assertEqual(self.shell._print_runnable_payloads(), NO_PAYLOAD_HANDLER_MSG)
        self.assertEqual(self.shell.write("/tmp/x", "data"), NO_TRANSFER_HANDLER_MSG)

        self.shell.identify_os()
        self.assertEqual(self.shell.get_remote_user(), "unknown")
        self.assertEqual(
            repr(self.shell),
            '<local_exec_shell object (ruser: "unknown" | rsystem: "unknown")>',
        )

    def test_identify_linux(self):
        shell = LinuxExecShell(MockVuln(), None, None)

        self.assertIn(f'ruser: "{getpass.getuser()}"', str(shell))
        self.assertEqual(shell.get_unlink_command(), "rm -rf %s")
        self.assertEqual(shell.get_read_command("/etc/passwd"), "cat %s")

    def test_identify_windows(self):
        shell = WindowsExecShell(MockVuln(), None, None)
        shell.identify_os()

        self.assertEqual(
            shell.get_remote_user(),
            shell.execute(r"echo %USERDOMAIN%\%USERNAME%").strip(),
        )
        self.assertEqual(shell._rSystemName, "%COMPUTERNAME%")
        self.assertEqual(shell.get_unlink_command(), "del %s")
        self.assertEqual(shell.get_read_command("C:\\boot.ini"), "type %s")
        self.assertEqual(shell.get_read_command("C:\\my file.txt"), 'type "%s"')

    def test_read(self):
        path = Path(self.directory, "my file.txt")
        path.write_text("first line\nsecond line which is long\n")

        with self.assertLogs("w3af.core.data.kb.decorators", level="DEBUG") as logs:
            content = self.shell.read(str(path))

        self.assertEqual(content, "first line\nsecond line which is long\n")
        self.assertIn('"first linesecond line whi..."', logs.output[0])

    def test_unlink(self):
        path = Path(self.directory, "remove-me")
        path.write_text("x")

        self.shell.unlink(str(path))

        self.assertFalse(path.exists())

    def test_download(self):
        remote = Path(self.directory, "remote.txt")
        remote.write_text("remote content")
        local = Path(self.directory, "local.txt")

        self.assertEqual(self.shell.download(str(remote), str(local)), "Success.")
        self.assertEqual(local.read_text(), "remote content")

    def test_download_missing_remote_file(self):
        local = Path(self.directory, "local.txt")
        missing = str(Path(self.directory, "missing"))

        self.assertEqual(
            self.shell.download(missing, str(local)), "Remote file does not exist."
        )

    def test_download_to_invalid_local_file(self):
        remote = Path(self.directory, "remote.txt")
        remote.write_text("remote content")
        local = Path(self.directory, "missing-dir", "local.txt")

        self.assertEqual(
            self.shell.download(str(remote), str(local)),
            "Failed to open local file for writing.",
        )

    def test_upload_missing_local_file(self):
        self.assertEqual(
            self.shell.upload(str(Path(self.directory, "missing")), "/tmp/remote"),
            "Failed to open local file for reading.",
        )

    def test_upload_reports_write_result(self):
        local = Path(self.directory, "local.txt")
        local.write_text("content")

        self.assertEqual(
            self.shell.upload(str(local), "/tmp/remote"), NO_TRANSFER_HANDLER_MSG
        )

    def test_write_without_transfer_methods(self):
        self.shell._payload_transfer_factory = TransferFactory()

        self.assertEqual(
            self.shell.write("/tmp/remote", "data"), "No transfer method is available."
        )

    def test_write_with_failing_transfer_handler(self):
        handler = DirectoryTransferHandler(self.directory, can_transfer=False)
        self.shell._payload_transfer_factory = TransferFactory(handler)

        self.assertEqual(
            self.shell.write("/tmp/remote", "data"),
            "Failed to transfer, the transfer handler failed.",
        )

    def test_write_and_upload(self):
        handler = DirectoryTransferHandler(self.directory)
        factory = TransferFactory(handler)
        self.shell._payload_transfer_factory = factory
        local = Path(self.directory, "local.txt")
        local.write_text("uploaded content")

        self.assertEqual(
            self.shell.write("/tmp/written.txt", "written content"),
            "File upload was successful.",
        )
        self.assertEqual(
            self.shell.upload(str(local), "/tmp/uploaded.txt"),
            "File upload was successful.",
        )

        self.assertEqual(factory.exec_method, self.shell.execute)
        self.assertEqual(
            Path(self.directory, "written.txt").read_text(), "written content"
        )
        self.assertEqual(
            Path(self.directory, "uploaded.txt").read_text(), "uploaded content"
        )

    def test_user_input_read(self):
        path = Path(self.directory, "file.txt")
        path.write_text("file content")

        self.assertEqual(
            self.shell.generic_user_input("read", [str(path)]), "file content"
        )
        self.assertIn(
            "Only one parameter is expected",
            self.shell.generic_user_input("read", ["a", "b"]),
        )

    def test_user_input_write_and_upload(self):
        local = Path(self.directory, "local.txt")
        local.write_text("content")

        self.assertEqual(
            self.shell.generic_user_input("write", ["/tmp/x", "data"]),
            NO_TRANSFER_HANDLER_MSG,
        )
        self.assertEqual(
            self.shell.generic_user_input("upload", [str(local), "/tmp/x"]),
            NO_TRANSFER_HANDLER_MSG,
        )

    def test_user_input_execute(self):
        for command in ("e", "exec", "execute"):
            self.assertEqual(
                self.shell.generic_user_input(command, ["echo", "w3af"]), "w3af\n"
            )

    def test_user_input_unknown_command(self):
        self.assertEqual(
            self.shell.generic_user_input("write", ["only-one"]),
            'Command "write" not found. Please type "help".',
        )
