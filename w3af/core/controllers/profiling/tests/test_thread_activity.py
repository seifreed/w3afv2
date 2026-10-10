"""
test_thread_activity.py

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

import threading
import unittest

from w3af.core.controllers.profiling import thread_activity
from w3af.core.controllers.profiling.thread_activity import (
    get_thread_name,
    start_thread_stack_dump,
    stop_thread_stack_dump,
)

from .profiling_output import (
    environment_variables,
    output_files,
    read_json_output,
    remove_output_files,
)


class TestThreadActivity(unittest.TestCase):
    def setUp(self):
        remove_output_files(thread_activity.PROFILING_OUTPUT_FMT)
        self.release = threading.Event()
        self.worker = threading.Thread(
            target=self.wait_for_release, name="profiled-worker"
        )
        self.worker.start()

    def tearDown(self):
        thread_activity.cancel_thread(thread_activity.SAVE_THREAD_PTR)
        self.release.set()
        self.worker.join(timeout=60)
        remove_output_files(thread_activity.PROFILING_OUTPUT_FMT)

    def wait_for_release(self):
        self.release.wait(timeout=60)

    def test_get_thread_name_finds_the_thread(self):
        name = get_thread_name(threading.enumerate(), self.worker.ident)

        self.assertEqual(name, "profiled-worker")

    def test_get_thread_name_of_unknown_thread_is_none(self):
        self.assertIsNone(get_thread_name(threading.enumerate(), -1))

    def test_profiling_disabled_does_nothing(self):
        with environment_variables(W3AF_THREAD_ACTIVITY="0"):
            start_thread_stack_dump()
            stop_thread_stack_dump()

        self.assertEqual(thread_activity.SAVE_THREAD_PTR, [])
        self.assertEqual(output_files(thread_activity.PROFILING_OUTPUT_FMT), [])

    def test_profiling_enabled_dumps_the_stack_of_every_thread(self):
        with environment_variables(W3AF_THREAD_ACTIVITY="1"):
            start_thread_stack_dump()

            self.assertEqual(len(thread_activity.SAVE_THREAD_PTR), 1)

            remove_output_files(thread_activity.PROFILING_OUTPUT_FMT)
            stop_thread_stack_dump()

        self.assertEqual(thread_activity.SAVE_THREAD_PTR, [])
        data = read_json_output(thread_activity.PROFILING_OUTPUT_FMT)
        worker_data = data[f"{self.worker.ident:x}"]
        self.assertEqual(worker_data["name"], "profiled-worker")
        self.assertIn("wait_for_release", "".join(worker_data["traceback"]))
        self.assertIn(f"{threading.get_ident():x}", data)
