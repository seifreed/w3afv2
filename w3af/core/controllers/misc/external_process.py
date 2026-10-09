"""
external_process.py

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

import os
import shutil
import threading
from asyncio.subprocess import DEVNULL, PIPE, STDOUT
from dataclasses import dataclass

from psutil import Popen

__all__ = [
    "DEVNULL",
    "PIPE",
    "STDOUT",
    "ExecutableNotFoundError",
    "ProcessResult",
    "ProcessTimeoutError",
    "resolve_executable",
    "run_process",
    "start_process",
]


class ExecutableNotFoundError(OSError):
    """Raised when the program to run is not installed or not executable."""


class ProcessTimeoutError(Exception):
    """Raised when a program does not finish within the allowed time."""


@dataclass(frozen=True)
class ProcessResult:
    returncode: int
    stdout: str | bytes | None
    stderr: str | bytes | None


def resolve_executable(program):
    """
    :param program: An absolute path, or a program name looked up in PATH.
    :return: The absolute path to the executable.
    :raises ExecutableNotFoundError: If it can not be found or executed.
    """
    if os.path.isabs(program):
        if os.path.isfile(program) and os.access(program, os.X_OK):
            return program
        raise ExecutableNotFoundError(f"{program} is not an executable file")

    path = shutil.which(program)
    if path is None:
        raise ExecutableNotFoundError(f"{program} was not found in PATH")

    return os.path.abspath(path)


def start_process(argv, **popen_kwargs):
    """
    Start ``argv`` without a shell. The first element is resolved to an
    absolute executable path, the rest are passed verbatim as arguments, so
    nothing in them is ever interpreted by a shell.

    :return: A Popen-compatible process object.
    """
    if isinstance(argv, (str, bytes)):
        raise TypeError("argv must be a sequence of arguments, not a string")

    command = [resolve_executable(argv[0]), *(str(arg) for arg in argv[1:])]
    return Popen(command, **popen_kwargs)


def run_process(argv, *, timeout=None, text=True, stdout=PIPE, stderr=PIPE):
    """
    Run ``argv`` to completion (see start_process) and collect its output.

    :param timeout: Seconds to wait before killing the process.
    :raises ProcessTimeoutError: If the timeout expired.
    """
    with start_process(
        argv, stdin=DEVNULL, stdout=stdout, stderr=stderr, text=text
    ) as process:
        expired = threading.Event()

        def kill_on_timeout():
            expired.set()
            process.kill()

        timer = threading.Timer(timeout, kill_on_timeout) if timeout else None
        if timer is not None:
            timer.start()

        try:
            out, err = process.communicate()
        finally:
            if timer is not None:
                timer.cancel()

    if expired.is_set():
        raise ProcessTimeoutError(f"{argv[0]} did not finish in {timeout} seconds")

    return ProcessResult(process.returncode, out, err)
