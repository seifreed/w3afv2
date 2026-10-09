"""
unixctrl.py

Copyright 2008 Andres Riancho

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
import termios
import tty

from w3af.core.ui.console.io.common import (
    KEY_DOWN,
    KEY_END,
    KEY_HOME,
    KEY_LEFT,
    KEY_RIGHT,
    KEY_UP,
)

LONGEST_SEQUENCE = 5

CSI = "\x1b["
CSI_CUB = CSI + "%iD"

SEQ_PREFIX = "\x1b"


def read(amt):
    return sys.stdin.read(amt)


old_settings = None


def set_raw_input_mode(raw):
    """
    Sets the raw input mode for the linux terminal.

    :param raw: Boolean to indicate if we want to turn raw mode on or off.
    """
    try:
        input_fd = sys.stdin.fileno()
    except OSError:
        return

    if not os.isatty(input_fd):
        return

    global old_settings

    if raw and old_settings is None:
        old_settings = termios.tcgetattr(input_fd)
        tty.setraw(input_fd)

    elif not raw and old_settings is not None:
        termios.tcsetattr(input_fd, termios.TCSADRAIN, old_settings)
        old_settings = None


def normalizeSequence(sequence):
    if sequence in (KEY_UP, KEY_DOWN, KEY_LEFT, KEY_RIGHT):
        return sequence
    map = {"\x1b[7~": KEY_HOME, "\x1b[8~": KEY_END}
    if sequence in map:
        return map[sequence]
    return None


def moveBack(steps=1):
    if steps > 0:
        sys.stdout.write(CSI_CUB % steps)


def clearScreen():
    """Clears the screen"""
    sys.stdout.write(SEQ_PREFIX + "[H" + SEQ_PREFIX + "[2J")
