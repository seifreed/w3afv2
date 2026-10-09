"""
tty.py

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
import sys

from w3af.core.ui.console.io import unixctrl


class TTYStdin:
    """
    sys.stdin backed by the slave end of a real pseudo-terminal. read() is
    unbuffered (os.read on the tty) so the console code never blocks waiting
    for a read-ahead buffer to fill.
    """

    def __init__(self, slave_fd):
        self._fd = slave_fd

    def fileno(self):
        return self._fd

    def read(self, amount):
        return os.read(self._fd, amount).decode("latin-1")


class RealTTY:
    """
    A real pseudo-terminal: sys.stdin reads from the slave end and the test
    writes the user's keystrokes into the master end.
    """

    def __init__(self):
        self.master, self.slave = os.openpty()
        self.stdin = TTYStdin(self.slave)

    def send(self, text):
        os.write(self.master, text.encode("latin-1"))

    def close(self):
        os.close(self.slave)
        os.close(self.master)

    @classmethod
    def as_stdin(cls, test_case):
        """
        Make a new pseudo-terminal the console's stdin while test_case runs,
        leaving the terminal out of raw mode afterwards.
        """
        terminal = cls()
        test_case.addCleanup(terminal.close)
        test_case.addCleanup(setattr, sys, "stdin", sys.stdin)
        test_case.addCleanup(unixctrl.set_raw_input_mode, False)

        unixctrl.old_settings = None
        sys.stdin = terminal.stdin
        return terminal
