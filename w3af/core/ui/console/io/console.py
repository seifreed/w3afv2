"""
console.py

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

import importlib
import os
import sys

from w3af.core.ui.console.io.common import (
    KEY_BACKSPACE,
    KEY_DOWN,
    KEY_LEFT,
    KEY_RIGHT,
    KEY_UP,
)

# The terminal control functions depend on the platform: termios on unix,
# msvcrt on Windows
_platform = importlib.import_module(
    "w3af.core.ui.console.io.winctrl"
    if sys.platform == "win32"
    else "w3af.core.ui.console.io.unixctrl"
)
read = _platform.read
set_raw_input_mode = _platform.set_raw_input_mode
normalizeSequence = _platform.normalizeSequence
moveBack = _platform.moveBack
clearScreen = _platform.clearScreen
SEQ_PREFIX = _platform.SEQ_PREFIX
LONGEST_SEQUENCE = _platform.LONGEST_SEQUENCE

__all__ = [
    "KEY_BACKSPACE",
    "KEY_DOWN",
    "KEY_LEFT",
    "KEY_RIGHT",
    "KEY_UP",
    "bell",
    "clearScreen",
    "getch",
    "moveBack",
    "set_raw_input_mode",
    "terminal_size",
    "write",
    "writeln",
]

DEFAULT_TERMINAL_SIZE = (80, 25)
STANDARD_FDS = (0, 1, 2)

CTRL_CODES = list(range(1, 27))
CTRL_CODES.remove(9)
CTRL_CODES.remove(13)


def sync_with_output_manager(func):
    """
    Given that the output manager has been migrated into a producer/consumer
    model, the messages that are sent to it are added to a Queue and printed
    "at a random time". The issue with this is that NOT EVERYTHING YOU SEE IN
    THE CONSOLE is printed using the om (see functions below), which ends up
    with unordered messages printed to the console.
    """

    def output_manager_wrapper(output_manager, *args, **kwds):
        output_manager.process_all_messages()
        return func(output_manager, *args, **kwds)

    return output_manager_wrapper


@sync_with_output_manager
def write(output_manager, s):
    if len(s):
        sys.stdout.write(s)


@sync_with_output_manager
def writeln(output_manager, s=""):
    sys.stdout.write(s + "\n\r")


@sync_with_output_manager
def bell(output_manager):
    sys.stdout.write("\x07")


@sync_with_output_manager
def getch(output_manager, buf=None):
    try:
        ch = read(1)
    except KeyboardInterrupt:
        return getch(output_manager, buf)
    if ch == SEQ_PREFIX:
        buf = [ch]
        result = getch(output_manager, buf)
    elif buf is not None:
        buf.append(ch)
        strval = "".join(buf)
        posixVal = normalizeSequence(strval)
        if posixVal:
            return posixVal
        elif len(buf) > LONGEST_SEQUENCE:
            return getch(output_manager)
        else:
            return getch(output_manager, buf)
    elif len(ch) and ord(ch) in CTRL_CODES:
        result = "^" + chr(ord(ch) + 64)
    else:
        result = ch

    return result


def terminal_size(fds=STANDARD_FDS):
    """
    :param fds: The file descriptors to query, the first terminal wins
    :return: The (columns, rows) of the terminal, read from the first of fds
             which is a terminal, then from the COLUMNS and LINES environment
             variables, or a default size.
    """
    for fd in fds:
        try:
            size = os.get_terminal_size(fd)
        except OSError:
            continue
        return size.columns, size.lines

    try:
        return int(os.environ["COLUMNS"]), int(os.environ["LINES"])
    except KeyError:
        return DEFAULT_TERMINAL_SIZE
