"""
test_io.py

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

import io
import os
import signal
import sys
import termios
import threading
import time
import unittest
from contextlib import redirect_stdout

import w3af.core.controllers.output_manager as om
import w3af.core.ui.console.io.console as term
from w3af.core.ui.console.io import unixctrl
from w3af.core.ui.console.io.common import (
    KEY_BACKSPACE,
    KEY_DOWN,
    KEY_END,
    KEY_HOME,
    KEY_LEFT,
    KEY_RIGHT,
    KEY_UP,
)
from w3af.core.ui.console.tests.tty import RealTTY, TTYStdin

LFLAG = 3
HOME_SEQUENCE = "\x1b[7~"


class TestUnixTTY(unittest.TestCase):
    def setUp(self):
        self.tty = RealTTY.as_stdin(self)

    def type_keys(self, keys):
        # The console reads keystrokes with the terminal in raw mode, without
        # it the tty would hold them until a newline is typed
        unixctrl.set_raw_input_mode(True)
        self.tty.send(keys)

    def test_read_from_the_terminal(self):
        self.type_keys("abc")
        self.assertEqual(unixctrl.read(3), "abc")

    def test_raw_mode_round_trip_on_a_real_tty(self):
        self.assertTrue(os.isatty(sys.stdin.fileno()))

        before = termios.tcgetattr(sys.stdin.fileno())
        unixctrl.set_raw_input_mode(True)
        self.assertIsNotNone(unixctrl.old_settings)
        raw = termios.tcgetattr(sys.stdin.fileno())
        self.assertNotEqual(before, raw)

        unixctrl.set_raw_input_mode(False)
        self.assertIsNone(unixctrl.old_settings)
        restored = termios.tcgetattr(sys.stdin.fileno())
        # The kernel may flag pending input (PENDIN) when the mode changes
        restored[LFLAG] &= ~termios.PENDIN
        self.assertEqual(restored, before)

    def test_raw_mode_is_ignored_when_stdin_has_no_file_descriptor(self):
        sys.stdin = io.StringIO()
        unixctrl.set_raw_input_mode(True)
        self.assertIsNone(unixctrl.old_settings)

    def test_raw_mode_is_ignored_when_stdin_is_not_a_tty(self):
        read_fd, write_fd = os.pipe()
        self.addCleanup(os.close, write_fd)
        self.addCleanup(os.close, read_fd)
        sys.stdin = TTYStdin(read_fd)

        unixctrl.set_raw_input_mode(True)
        self.assertIsNone(unixctrl.old_settings)

    def test_getch_reads_control_codes_and_sequences(self):
        self.type_keys("a")
        self.assertEqual(term.getch(om.manager), "a")

        self.tty.send("\x01")  # Ctrl+A
        self.assertEqual(term.getch(om.manager), "^A")

        self.tty.send(KEY_UP)
        self.assertEqual(term.getch(om.manager), KEY_UP)

        self.tty.send(HOME_SEQUENCE)
        self.assertEqual(term.getch(om.manager), KEY_HOME)

    def test_getch_retries_after_an_interrupt(self):
        unixctrl.set_raw_input_mode(True)
        main_thread = threading.get_ident()

        def interrupt_then_type():
            # Ctrl+C reaches the console as SIGINT while getch() waits for a
            # key: it must keep waiting and return the next key
            time.sleep(0.3)
            signal.pthread_kill(main_thread, signal.SIGINT)
            time.sleep(0.3)
            self.tty.send("x")

        typist = threading.Thread(target=interrupt_then_type)
        typist.start()
        self.addCleanup(typist.join)

        self.assertEqual(term.getch(om.manager), "x")

    def test_getch_discards_unknown_escape_sequences(self):
        # An escape sequence longer than LONGEST_SEQUENCE is dropped, then the
        # following real keystroke is returned
        self.type_keys("\x1b" + "[" * unixctrl.LONGEST_SEQUENCE + "z")
        self.assertEqual(term.getch(om.manager), "z")

    def test_terminal_size_of_a_real_tty(self):
        termios.tcsetwinsize(self.tty.slave, (24, 100))
        self.assertEqual(
            term.terminal_size([self.tty.master + 1000, self.tty.slave]), (100, 24)
        )

    def test_terminal_size_without_a_terminal(self):
        environ = dict(os.environ)
        self.addCleanup(os.environ.update, environ)
        self.addCleanup(os.environ.clear)

        os.environ.pop("COLUMNS", None)
        os.environ.pop("LINES", None)
        self.assertEqual(term.terminal_size([]), term.DEFAULT_TERMINAL_SIZE)

        os.environ["COLUMNS"], os.environ["LINES"] = "120", "40"
        self.assertEqual(term.terminal_size([]), (120, 40))


class TestTerminalOutput(unittest.TestCase):
    def test_output_helpers_write_escape_codes(self):
        written = io.StringIO()
        with redirect_stdout(written):
            term.write(om.manager, "hi")
            term.write(om.manager, "")  # empty strings are skipped
            term.writeln(om.manager, "line")
            term.bell(om.manager)
            term.moveBack(3)
            term.moveBack(0)  # non-positive moves write nothing
            term.clearScreen()

        output = written.getvalue()
        self.assertIn("hi", output)
        self.assertIn("line\n\r", output)
        self.assertIn("\x07", output)
        self.assertIn("\x1b[3D", output)
        self.assertIn("\x1b[H\x1b[2J", output)


class TestWinCtrlKeyMapping(unittest.TestCase):
    """
    winctrl.py is Windows only, but its key-mapping logic is pure and can be
    imported and tested on any platform.
    """

    def setUp(self):
        from w3af.core.ui.console.io import winctrl

        self.winctrl = winctrl

    def test_normalize_known_sequences(self):
        self.assertEqual(self.winctrl.normalizeSequence("\xe0\x48"), KEY_UP)
        self.assertEqual(self.winctrl.normalizeSequence("\xe0\x50"), KEY_DOWN)
        self.assertEqual(self.winctrl.normalizeSequence("\xe0\x4d"), KEY_RIGHT)
        self.assertEqual(self.winctrl.normalizeSequence("\xe0\x4b"), KEY_LEFT)
        self.assertEqual(self.winctrl.normalizeSequence("\xe0\x47"), KEY_HOME)
        self.assertEqual(self.winctrl.normalizeSequence("\xe0\x4f"), KEY_END)

    def test_normalize_unknown_sequence(self):
        self.assertIsNone(self.winctrl.normalizeSequence("\xe0\x00"))

    def test_read_nothing_needs_no_console(self):
        self.assertEqual(self.winctrl.read(0), "")

    def test_output_helpers(self):
        written = io.StringIO()
        with redirect_stdout(written):
            self.winctrl.moveBack(2)
            self.winctrl.clearScreen()
        self.assertEqual(written.getvalue(), "\x08\x08")

    def test_set_raw_input_mode_is_a_noop(self):
        self.assertIsNone(self.winctrl.set_raw_input_mode(True))

    def test_backspace_is_reported_consistently(self):
        self.assertEqual(KEY_BACKSPACE, "\x7f")
