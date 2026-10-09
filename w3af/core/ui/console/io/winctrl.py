"""
winctrl.py

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
import sys

from w3af.core.ui.console.io.common import (
    KEY_DOWN,
    KEY_END,
    KEY_HOME,
    KEY_LEFT,
    KEY_RIGHT,
    KEY_UP,
)

SEQ_PREFIX = "\xe0"
LONGEST_SEQUENCE = 2

win2UnixMap = {
    "\xe0\x48": KEY_UP,
    "\xe0\x50": KEY_DOWN,
    "\xe0\x4d": KEY_RIGHT,
    "\xe0\x4b": KEY_LEFT,
    "\xe0\x47": KEY_HOME,
    "\xe0\x4f": KEY_END,
}


def read(amt):
    """
    Read amt characters from the Windows console. msvcrt only exists on
    Windows, it is imported when the first character is read so the key
    mapping in this module can be used (and tested) on every platform.
    """
    return "".join(importlib.import_module("msvcrt").getwch() for _ in range(amt))


def set_raw_input_mode(raw):
    """
    The Windows console already delivers every key press, there is no raw
    mode to switch.
    """


def normalizeSequence(seq):
    return win2UnixMap.get(seq)


def moveBack(steps=1):
    sys.stdout.write("\x08" * steps)


def clearScreen():
    """
    Clearing the Windows console is not supported.
    """
