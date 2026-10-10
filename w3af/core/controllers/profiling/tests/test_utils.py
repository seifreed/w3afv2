"""
test_utils.py

Copyright 2026 Andres Riancho

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
import unittest

from w3af.core.controllers.profiling.utils import (
    cancel_thread,
    dump_data_every_thread,
    get_filename_fmt,
)

from .profiling_output import environment_variables


class TestUtils(unittest.TestCase):
    def setUp(self):
        self.save_thread_ptr = []
        self.calls = []

    def tearDown(self):
        cancel_thread(self.save_thread_ptr)

    def test_get_filename_fmt(self):
        pid, date = get_filename_fmt()

        self.assertEqual(pid, os.getpid())
        self.assertRegex(date, r"^\d{4}-\d{2}-\d{2}-\d{2}_\d{2}$")

    def test_dump_data_every_thread_runs_func_and_schedules_timer(self):
        dump_data_every_thread(self.record_call, 2, self.save_thread_ptr)

        self.assertEqual(self.calls, ["called"])
        (timer,) = self.save_thread_ptr
        self.assertTrue(timer.is_alive())
        self.assertTrue(timer.daemon)
        self.assertEqual(timer.name, "ProfilingDumpData")
        self.assertEqual(timer.interval, 120)

    def test_dump_data_every_thread_replaces_previous_timer(self):
        dump_data_every_thread(self.record_call, 2, self.save_thread_ptr)
        first_timer = self.save_thread_ptr[0]

        dump_data_every_thread(self.record_call, 2, self.save_thread_ptr)

        self.assertEqual(len(self.save_thread_ptr), 1)
        self.assertIsNot(self.save_thread_ptr[0], first_timer)
        first_timer.cancel()

    def test_dump_data_every_thread_survives_keyboard_interrupt(self):
        dump_data_every_thread(self.interrupted, 2, self.save_thread_ptr)

        self.assertEqual(self.calls, ["interrupted"])
        self.assertEqual(len(self.save_thread_ptr), 1)
        self.assertTrue(self.save_thread_ptr[0].is_alive())

    def test_cancel_thread_stops_timer_and_empties_pointer(self):
        dump_data_every_thread(self.record_call, 2, self.save_thread_ptr)
        timer = self.save_thread_ptr[0]

        cancel_thread(self.save_thread_ptr)
        timer.join(timeout=5)

        self.assertFalse(timer.is_alive())
        self.assertEqual(self.save_thread_ptr, [])

    def test_cancel_thread_without_timer_is_noop(self):
        cancel_thread(self.save_thread_ptr)

        self.assertEqual(self.save_thread_ptr, [])

    def record_call(self):
        self.calls.append("called")

    def interrupted(self):
        self.calls.append("interrupted")
        raise KeyboardInterrupt()


class TestEnvironmentVariables(unittest.TestCase):
    def test_variables_are_set_inside_and_restored_after(self):
        with environment_variables(W3AF_TEST_EXISTING="inner", W3AF_TEST_NEW="1"):
            self.assertEqual(os.environ["W3AF_TEST_EXISTING"], "inner")
            self.assertEqual(os.environ["W3AF_TEST_NEW"], "1")

        self.assertEqual(os.environ["W3AF_TEST_EXISTING"], "outer")
        self.assertNotIn("W3AF_TEST_NEW", os.environ)

    def setUp(self):
        os.environ["W3AF_TEST_EXISTING"] = "outer"

    def tearDown(self):
        del os.environ["W3AF_TEST_EXISTING"]
