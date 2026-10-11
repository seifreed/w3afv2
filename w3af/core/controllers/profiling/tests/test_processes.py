"""
test_processes.py

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

import multiprocessing
import unittest

from w3af.core.controllers.profiling import processes
from w3af.core.controllers.profiling.processes import (
    start_process_dump,
    stop_process_dump,
)

from .profiling_output import (
    environment_variables,
    output_files,
    read_json_output,
    remove_output_files,
)


class TestProcesses(unittest.TestCase):
    def setUp(self):
        remove_output_files(processes.PROFILING_OUTPUT_FMT)
        self.release = multiprocessing.Event()
        self.child = multiprocessing.Process(
            target=self.release.wait,
            name="profiled-child",
            args=(60,),
            daemon=True,
        )
        self.child.start()

    def tearDown(self):
        processes.cancel_thread(processes.SAVE_PROCESS_PTR)
        self.release.set()
        self.child.join(timeout=60)
        if self.child.is_alive():
            self.child.terminate()
            self.child.join()
        remove_output_files(processes.PROFILING_OUTPUT_FMT)

    def test_profiling_disabled_does_nothing(self):
        with environment_variables(W3AF_PROCESSES="0"):
            start_process_dump()
            stop_process_dump()

        self.assertEqual(processes.SAVE_PROCESS_PTR, [])
        self.assertEqual(output_files(processes.PROFILING_OUTPUT_FMT), [])

    def test_profiling_enabled_dumps_the_active_children(self):
        with environment_variables(W3AF_PROCESSES="1"):
            start_process_dump()

            self.assertEqual(len(processes.SAVE_PROCESS_PTR), 1)

            remove_output_files(processes.PROFILING_OUTPUT_FMT)
            stop_process_dump()

        self.assertEqual(processes.SAVE_PROCESS_PTR, [])
        child_data = read_json_output(processes.PROFILING_OUTPUT_FMT)[
            str(self.child.pid)
        ]
        self.assertEqual(
            child_data,
            {
                "name": "profiled-child",
                "daemon": True,
                "exitcode": None,
            },
        )
