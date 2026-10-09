"""
test_auto_update.py

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

import w3af.core.controllers.output_manager as om
from w3af.core.ui.console.auto_update.auto_update import ConsoleUIUpdater, ask
from w3af.core.ui.console.tests.helper import ConsoleTestHelper


class TestConsoleUIUpdater(ConsoleTestHelper):
    """
    The console asks the user, through stdin, before updating and before
    showing the update log.
    """

    def setUp(self):
        super().setUp()
        # The updater talks to the user through the console output plugin
        om.manager.set_output_plugins(["console"])

    def answer(self, response):
        self.addCleanup(setattr, sys, "stdin", sys.stdin)
        sys.stdin = io.StringIO(response + "\n")

    def output(self):
        om.manager.process_all_messages()
        return "".join(self._captured_stdout.messages)

    def test_ask_accepts_yes(self):
        self.answer("Yes")
        self.assertTrue(ask("Update?"))
        self.assertIn("Update? [y/N] ", self.output())

    def test_ask_defaults_to_no(self):
        self.answer("")
        self.assertFalse(ask("Update?"))

    def test_show_log_when_the_user_wants_it(self):
        updater = ConsoleUIUpdater(force=False)
        show_log = updater._callbacks["callback_onupdate_show_log"]

        self.answer("y")
        show_log("Show the changes?", lambda: "commit abc: fix")
        self.assertIn("commit abc: fix", self.output())

    def test_log_is_not_shown_when_declined(self):
        updater = ConsoleUIUpdater(force=False)
        show_log = updater._callbacks["callback_onupdate_show_log"]

        self.answer("n")
        show_log("Show the changes?", lambda: "commit abc: fix")
        self.assertNotIn("commit abc: fix", self.output())

    def test_update_confirmation_asks_the_user(self):
        updater = ConsoleUIUpdater(force=False)
        self.assertIs(updater._callbacks["callback_onupdate_confirm"], ask)

    def test_update_output_needs_no_handling(self):
        self.assertIsNone(ConsoleUIUpdater(force=False)._handle_update_output("x"))
