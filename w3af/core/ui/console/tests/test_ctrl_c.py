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

import io
import sys
import threading
import time

from w3af.core.ui.console.console_ui import ConsoleUI
from w3af.core.ui.console.io import unixctrl
from w3af.core.ui.console.root_menu import rootMenu, stdin_is_terminal
from w3af.core.ui.console.tests.helper import ConsoleTestHelper
from w3af.core.ui.console.tests.tty import RealTTY
from w3af.tests.helpers.sqli_site import SQLInjectionSite

ROOT_WAIT_SECONDS = rootMenu.MAX_WAIT_FOR_START


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
        self.console._output_manager.process_all_messages()
        return "".join(self._captured_stdout.messages)

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
        # The scan thread is alive but the core never reaches "running"
        release = threading.Event()
        scan_thread = threading.Thread(target=release.wait)
        scan_thread.start()
        self.addCleanup(scan_thread.join)
        self.addCleanup(release.set)

        self.menu.MAX_WAIT_FOR_START = 0.2
        self.assertFalse(self.menu.wait_for_start(scan_thread))

    def test_wait_for_start_stops_when_the_scan_thread_ends(self):
        scan_thread = threading.Thread(target=lambda: None)
        scan_thread.start()
        scan_thread.join()

        started = time.monotonic()
        self.assertFalse(self.menu.wait_for_start(scan_thread))
        self.assertLess(time.monotonic() - started, 1)

    def _run_console(self, commands):
        console = ConsoleUI(commands=commands, do_upd=False)
        started = time.monotonic()
        console.sh()
        return "".join(self._captured_stdout.messages), time.monotonic() - started

    def test_start_without_target_fails_fast(self):
        output, elapsed = self._run_console(["start", "exit"])
        self.assertIn("The scan failed to start.", output)
        self.assertLess(elapsed, ROOT_WAIT_SECONDS)

    def test_start_without_output_plugins_warns(self):
        output, _ = self._run_console(
            ["plugins", "output !all", "back", "start", "exit"]
        )
        # Once from the plugins menu, once more when the scan is started
        self.assertEqual(
            output.count("Warning: You disabled the console output plugin."), 2
        )

    def test_stdin_is_terminal_under_pytest(self):
        # pytest captures stdin, so it is not a terminal
        self.assertFalse(stdin_is_terminal())

    def test_stdin_without_file_descriptor_is_not_a_terminal(self):
        self.addCleanup(setattr, sys, "stdin", sys.stdin)
        sys.stdin = io.StringIO()
        self.assertFalse(stdin_is_terminal())


class TestScanKeypressLoop(ConsoleTestHelper):
    """
    Type keys on a real pseudo-terminal while a scan is paused: the root menu
    keypress loop must dispatch them until the scan is resumed or stopped.
    """

    def setUp(self):
        super().setUp()
        self.tty = RealTTY.as_stdin(self)
        self.console = ConsoleUI(do_upd=False)
        self.menu = rootMenu("w3af", self.console, self.console._w3af)
        self.addCleanup(self.console._w3af.quit)
        self.menu._pause_scan()

    def _type_slowly(self, *keys, then_finish_scan=False):
        def typist():
            # The first select() call times out before the first key arrives
            time.sleep(0.7)
            for key in keys:
                self.tty.send(key)
                time.sleep(0.2)
            if then_finish_scan:
                self.console._w3af.status.stop()

        thread = threading.Thread(target=typist)
        thread.start()
        self.addCleanup(thread.join)

    def _output(self):
        self.console._output_manager.process_all_messages()
        return "".join(self._captured_stdout.messages)

    def test_keys_during_a_paused_scan(self):
        self.assertTrue(stdin_is_terminal())
        # Resuming marks the scan as running again, it ends when the scan does
        self._type_slowly("\r", "x", "P", "R", then_finish_scan=True)

        self.menu.handle_keypress_during_scan()

        output = self._output()
        self.assertIn("| Paused ", output)  # status for the enter key
        self.assertIn("Unknown key.", output)
        self.assertIn("The scan is already paused.", output)
        self.assertIn("The scan was resumed.", output)

    def test_ctrl_c_stops_the_scan(self):
        self._type_slowly("\x03")

        with self.assertRaises(KeyboardInterrupt):
            self.menu.handle_keypress_during_scan()

        # The terminal is back in its normal mode
        self.assertIsNone(unixctrl.old_settings)


class TestCtrlCDuringARealScan(ConsoleTestHelper):
    """
    Start a real scan from a terminal and press Ctrl+C while it runs. The local
    site holds every request after the index, so the scan is still running
    when the key is pressed.
    """

    def setUp(self):
        super().setUp()
        self.site = SQLInjectionSite.serve_for(self, hold_requests=True)
        self.tty = RealTTY.as_stdin(self)

    def _press_ctrl_c_once_running(self):
        deadline = time.monotonic() + rootMenu.MAX_WAIT_FOR_START
        while time.monotonic() < deadline:
            if self.console._w3af.status.is_running():
                break
            time.sleep(0.1)

        time.sleep(0.5)
        self.tty.send("\x03")
        # Let the held requests finish so the core can stop
        self.site.release()

    def test_ctrl_c_stops_the_running_scan(self):
        self.console = ConsoleUI(
            commands=[
                "plugins",
                "crawl web_spider",
                "back",
                "target",
                f"set target {self.site.url}",
                "back",
                "start",
                "exit",
            ],
            do_upd=False,
        )

        typist = threading.Thread(target=self._press_ctrl_c_once_running)
        typist.start()
        self.addCleanup(typist.join)

        self.console.sh()

        output = "".join(self._captured_stdout.messages)
        self.assertIn("User pressed Ctrl+C, stopping scan.", output)
