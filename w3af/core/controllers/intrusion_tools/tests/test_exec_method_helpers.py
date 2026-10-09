"""
test_exec_methodHelpers.py

Copyright 2011 Andres Riancho

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

import subprocess
import sys
import unittest

from w3af.core.controllers.exceptions import BaseFrameworkException
from w3af.core.controllers.intrusion_tools.exec_method_helpers import (
    get_remote_temp_file,
    os_detection_exec,
)

LINUX_SHELL = {
    "echo -n w3af": "w3af",
    "head -n 1 /etc/passwd": "root:x:0:0:root:/root:/bin/bash",
    "ls ": "ls: cannot access '/tmp/abc': No such file or directory",
}

WINDOWS_SHELL = {
    "echo -n w3af": "Command not found",
    "head -n 1 /etc/passwd": "Command not found",
    "type %SYSTEMROOT%\\win.ini": "; for 16-bit app support\r\n[fonts]",
    "echo /?": "Displays messages, or turns command-echoing on or off.\r\nECHO",
    "echo %TEMP%": "C:\\Windows\\Temp\r\n",
    "dir ": "File not found",
}


class RemoteShell:
    """
    Command executor for a remote host whose answers are known in advance:
    every command is answered with the output of the first registered
    command prefix it starts with.
    """

    def __init__(self, outputs):
        self._outputs = outputs
        self.executed = []

    def __call__(self, command):
        self.executed.append(command)
        for prefix, output in self._outputs.items():
            if command.startswith(prefix):
                return output
        return "foobarspameggs"


class TestExecHelpers(unittest.TestCase):

    @unittest.skipUnless(sys.platform.startswith("linux"), "Needs a Linux host")
    def test_os_detection_exec_local_linux(self):
        self.assertEqual(os_detection_exec(subprocess.getoutput), "linux")

    @unittest.skipUnless(sys.platform.startswith("linux"), "Needs a Linux host")
    def test_get_remote_temp_file_local_linux(self):
        tempfile = get_remote_temp_file(subprocess.getoutput)
        self.assertTrue(tempfile.startswith("/tmp/"))

    def test_os_detection_exec_linux(self):
        os = os_detection_exec(RemoteShell(LINUX_SHELL))
        self.assertEqual(os, "linux")

    def test_os_detection_exec_windows(self):
        exec_method = RemoteShell(WINDOWS_SHELL)
        os = os_detection_exec(exec_method)
        self.assertEqual(os, "windows")
        self.assertEqual(len(exec_method.executed), 4)

    def test_os_detection_exec_unknown(self):
        exec_method = RemoteShell({})
        self.assertRaises(BaseFrameworkException, os_detection_exec, exec_method)

    def test_get_remote_temp_file_linux(self):
        tempfile = get_remote_temp_file(RemoteShell(LINUX_SHELL))
        self.assertTrue(tempfile.startswith("/tmp/"))

    def test_get_remote_temp_file_windows(self):
        tempfile = get_remote_temp_file(RemoteShell(WINDOWS_SHELL))
        self.assertTrue(tempfile.startswith("C:\\Windows\\Temp\\"))

    def test_get_remote_temp_file_unknown(self):
        exec_method = RemoteShell({})
        self.assertRaises(BaseFrameworkException, get_remote_temp_file, exec_method)
