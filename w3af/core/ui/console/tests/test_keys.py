"""
test_keys.py

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
import sys
from pathlib import Path

from w3af.core.ui.console import console_ui
from w3af.core.ui.console.console_ui import ConsoleUI
from w3af.core.ui.console.io.common import (
    KEY_BACKSPACE,
    KEY_DOWN,
    KEY_LEFT,
    KEY_RIGHT,
    KEY_UP,
)
from w3af.core.ui.console.tests.helper import ConsoleTestHelper

CTRL_A = "\x01"
CTRL_C = "\x03"
CTRL_D = "\x04"
CTRL_E = "\x05"
CTRL_H = "\x08"
CTRL_L = "\x0c"
CTRL_W = "\x17"
TAB = "\t"
ENTER = "\r"
HOME_SEQUENCE = "\x1b[7~"
UNKNOWN_SEQUENCE = "\x1b[99999"
EXIT_MESSAGES = [
    line.strip()
    for line in Path(console_ui.__file__)
    .with_name("exitmessages.txt")
    .read_text()
    .splitlines()
    if line.strip()
]


class TestConsoleKeys(ConsoleTestHelper):
    """
    Type real key sequences into the console: the keys are read from stdin
    by the terminal layer (term.getch) and dispatched by ConsoleUI._handleKey,
    exactly like an interactive session.
    """

    def type_keys(self, *keys):
        self.addCleanup(setattr, sys, "stdin", sys.stdin)
        sys.stdin = io.StringIO("".join(keys))

        self.console = ConsoleUI(do_upd=False)
        self.console.sh()
        return "".join(self._captured_stdout.messages)

    def test_tab_completion(self):
        output = self.type_keys(
            "plug",
            TAB,  # single completion: "plugins "
            ENTER,
            TAB,  # empty line: every command is listed
            "zzz",
            TAB,  # no completion: bell
            CTRL_W,
            CTRL_W,
            "back",
            ENTER,
            "exit",
            ENTER,
        )
        self.assertIn("w3af/plugins>>> ", output)
        self.assertIn("audit", output)
        self.assertIn("\x07", output)

    def test_line_editing(self):
        output = self.type_keys(
            "exitx",
            KEY_BACKSPACE,  # "exit"
            KEY_LEFT,  # move inside the line
            KEY_LEFT,
            KEY_RIGHT,
            CTRL_A,  # line start...
            KEY_LEFT,  # ...where moving left rings the bell
            CTRL_E,  # line end...
            KEY_RIGHT,  # ...where moving right rings the bell
            CTRL_H,  # ^H deletes like backspace
            "t",
            HOME_SEQUENCE,  # escape sequence mapped to ^A
            CTRL_E,
            UNKNOWN_SEQUENCE,  # ignored escape sequence
            CTRL_L,  # clear screen and redraw the prompt
            KEY_BACKSPACE * 6,
            "exit",
            ENTER,
        )
        self.assertIn("\x1b[2J", output)
        self.assertIn("\x07", output)

    def test_history_navigation(self):
        output = self.type_keys(
            "keys",
            ENTER,
            "help",
            ENTER,
            "dra",  # a draft line which history navigation must restore
            KEY_UP,
            KEY_UP,
            KEY_UP,  # no older entry: bell
            KEY_DOWN,
            KEY_DOWN,  # back to the draft
            KEY_DOWN,  # no newer entry: bell
            CTRL_W,
            "exit",
            ENTER,
        )
        self.assertIn("\x07", output)

    def test_end_of_line_redraws_the_whole_tail(self):
        output = self.type_keys("hel", CTRL_A, CTRL_E, "p", ENTER, "exit", ENTER)
        # Moving to the line start goes back 3 columns, moving to the end must
        # re-print the 3 characters so the cursor really is at the end
        self.assertIn("\x1b[3Dhel", output)
        self.assertIn("Display key shortcuts.", output)

    def test_unbalanced_quotes(self):
        output = self.type_keys('print "unbalanced', ENTER, "exit", ENTER)
        self.assertIn("No closing quotation", output)

    def test_ctrl_c_and_ctrl_d_go_back_then_exit(self):
        output = self.type_keys("plugins", ENTER, CTRL_C, CTRL_D)
        self.assertIn("w3af/plugins>>> back", output)
        self.assertIn("w3af>>> exit", output)

    def test_unknown_command_reports_error(self):
        output = self.type_keys("nope", ENTER, "exit", ENTER)
        self.assertIn("Unknown command 'nope'", output)

    def test_back_at_the_root_menu_stays_there(self):
        output = self.type_keys("back", ENTER, "exit", ENTER)
        self.assertIn("w3af>>> back\r\nw3af>>> exit", output)

    def test_ctrl_c_clears_the_typed_line_before_going_back(self):
        output = self.type_keys("plugins", ENTER, "typed", CTRL_C, "exit", ENTER)
        # Each of the 5 typed characters is erased before "back" is issued
        erase = "\x1b[1D \x1b[1D"
        self.assertIn(f"w3af/plugins>>> typed{erase * 5}back", output)
        self.assertIn("w3af>>> exit", output)

    def test_ctrl_w_stops_at_punctuation(self):
        output = self.type_keys("print kb.", CTRL_W, CTRL_W, "kb", ENTER, "exit", ENTER)
        # "print kb." loses "." then "kb", leaving "print " to complete
        self.assertIn("w3af>>> print kb", output)

    def test_tab_without_completer_does_nothing(self):
        output = self.type_keys("print ", TAB, "kb", ENTER, "exit", ENTER)
        self.assertIn("knowledge_base", output)

    def test_completion_list_keeps_the_cursor_position(self):
        output = self.type_keys("prx", KEY_LEFT, TAB, CTRL_E, CTRL_W, "exit", ENTER)
        # Both "print" and "profiles" complete "pr": they are listed and the
        # line is redrawn with the cursor moved back before the "x"
        self.assertIn("print", output)
        self.assertIn("profiles", output)
        self.assertIn("prx\x1b[1D", output)

    def test_interrupting_a_command_closes_the_console(self):
        output = self.type_keys(
            "print (_ for _ in ()).throw(KeyboardInterrupt())", ENTER
        )
        # The interrupted command prints nothing, and the console still shuts
        # the core down and prints one of its exit messages
        self.assertNotIn("Unknown variable.", output)
        self.assertTrue(any(message in output for message in EXIT_MESSAGES))
