"""
local_shells.py

Copyright 2026 w3af contributors

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

Shells that work against the local machine, plus small implementations of the
collaborators the plugins layer injects into the data-layer shells. They let
the shell tests exercise real command execution and file access without a
vulnerable remote target.
"""

import subprocess
from pathlib import Path

from w3af.core.data.kb.exec_shell import ExecShell
from w3af.core.data.kb.read_shell import ReadShell
from w3af.core.exceptions import BaseFrameworkException


class LocalExecShell(ExecShell):
    """Runs every command with the local /bin/sh."""

    def execute(self, cmd):
        return subprocess.run(
            ["/bin/sh", "-c", cmd], capture_output=True, text=True, check=False
        ).stdout

    def get_name(self):
        return "local_exec_shell"


class LinuxExecShell(LocalExecShell):
    _os_detector = staticmethod(lambda execute: "linux")


class WindowsExecShell(LocalExecShell):
    _os_detector = staticmethod(lambda execute: "windows")


class DirectoryReadShell(ReadShell):
    """
    Reads "remote" files from a local directory: each remote path is stored
    in a local file named after the path with the separators replaced.
    """

    def __init__(self, vuln, directory):
        super().__init__(vuln, None, None)
        self.directory = Path(directory)

    def local_path(self, remote_path):
        name = remote_path.replace("/", "_").replace("\\", "_").replace(":", "_")
        return self.directory / name

    def add_file(self, remote_path, content):
        self.local_path(remote_path).write_text(content, encoding="utf-8")

    def read(self, filename):
        local_path = self.local_path(filename)
        if not local_path.exists():
            return ""
        return local_path.read_text(encoding="utf-8")


class DirectoryTransferHandler:
    """Transfers files into a local directory."""

    def __init__(self, directory, can_transfer=True):
        self.directory = Path(directory)
        self._can_transfer = can_transfer

    def can_transfer(self):
        return self._can_transfer

    def estimate_transfer_time(self, size):
        return size // 1024

    def transfer(self, content, remote_filename):
        Path(self.directory, Path(remote_filename).name).write_text(content)


class TransferFactory:
    """Mirrors payload_transfer_factory(exec_method, knowledge_base)."""

    def __init__(self, handler=None):
        self.handler = handler

    def __call__(self, exec_method, knowledge_base):
        self.exec_method = exec_method
        return self

    def get_transfer_handler(self):
        if self.handler is None:
            raise BaseFrameworkException("No transfer method is available.")
        return self.handler


class Payload:
    def __init__(self, desc, capability, function):
        self.desc = desc
        self.capability = capability
        self.function = function

    def get_desc(self):
        return self.desc


class PayloadCatalog:
    """
    Implements the payload handler protocol the plugins layer injects into
    Shell._payload_handler, backed by plain Python functions.
    """

    def __init__(self, payloads):
        self.payloads = payloads
        self.executed = []

    def get_payload_list(self):
        return list(self.payloads)

    def get_payload_desc(self, payload_name):
        return self.payloads[payload_name].get_desc()

    def get_payload_instance(self, payload_name, shell_obj):
        return self.payloads[payload_name]

    def runnable_payloads(self, shell_obj):
        return [
            name
            for name, payload in self.payloads.items()
            if hasattr(shell_obj, payload.capability)
        ]

    def exec_payload(self, shell_obj, payload_name, parameters):
        result = self.payloads[payload_name].function(shell_obj, *parameters)
        self.executed.append((payload_name, result))
        return result


def hostname(shell):
    return shell.execute("hostname").strip()


def port_check(shell, port):
    if not port.isdigit():
        raise ValueError(f'Invalid port "{port}".')
    return int(port)


def read_users(shell):
    return shell.read("/etc/passwd")


def payload_catalog():
    return PayloadCatalog(
        {
            "hostname": Payload("Show the hostname", "execute", hostname),
            "port_check": Payload("Check a port", "execute", port_check),
            "read_users": Payload("Read the users", "read", read_users),
            "screenshot": Payload("Take a screenshot", "screenshot", hostname),
        }
    )
