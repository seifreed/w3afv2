"""
test_ctrl_c.py

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

import w3af.core.controllers.output_manager as om
from w3af.core.ui.console.console_ui import ConsoleUI
from w3af.core.ui.console.root_menu import rootMenu, stdin_is_terminal
from w3af.core.ui.console.tests.helper import ConsoleTestHelper


class TestScanControl(ConsoleTestHelper):
    """
    Exercise the console scan-control handlers (the keypress actions used
    while a scan is running, including the Ctrl+C handler) directly against a
    real w3afCore.
    """

    def setUp(self):
        super().setUp()
        self.console = ConsoleUI(do_upd=False)
        self.menu = rootMenu("w3af", self.console, self.console._w3af)

    def tearDown(self):
        self.console._w3af.quit()
        super().tearDown()

    def _output(self):
        om.manager.process_all_messages()
        return "".join(self._mock_stdout.messages)

    def test_handle_scan_stop_reports_and_stops(self):
        self.menu.handle_scan_stop()
        self.assertIn("User pressed Ctrl+C, stopping scan.", self._output())

    def test_stop_scan_raises_keyboard_interrupt(self):
        with self.assertRaises(KeyboardInterrupt):
            self.menu._stop_scan()

    def test_unknown_key_during_scan_prints_help(self):
        self.menu._default_during_scan_handler()
        output = self._output()
        self.assertIn("pause the scan", output)
        self.assertIn("stop scan", output)

    def test_resume_when_not_paused(self):
        self.menu._resume_scan()
        self.assertIn("The scan is running. Can not resume.", self._output())

    def test_pause_and_resume(self):
        self.menu._pause_scan()
        self.assertIn("The scan was paused.", self._output())

        # Pausing again is a no-op with a message
        self.clear_stdout_messages()
        self.menu._pause_scan()
        self.assertIn("The scan is already paused.", self._output())

        # And now it can be resumed
        self.clear_stdout_messages()
        self.menu._resume_scan()
        self.assertIn("The scan was resumed.", self._output())

    def test_show_status(self):
        self.menu._show_status()
        # The idle core reports its status without raising
        self.assertIn("Stopped", self._output())

    def test_version_command(self):
        self.menu._cmd_version([])
        self.assertTrue(self._output().strip())

    def test_wait_for_start_times_out(self):
        self.menu.MAX_WAIT_FOR_START = 0.2
        self.assertFalse(self.menu.wait_for_start())

    def test_stdin_is_terminal_under_pytest(self):
        # pytest captures stdin, so it is not a terminal
        self.assertFalse(stdin_is_terminal())
