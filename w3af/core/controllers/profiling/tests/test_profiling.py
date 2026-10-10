"""
test_profiling.py

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

import tracemalloc
import unittest

import yappi

from w3af.core.controllers.profiling import (
    core_stats,
    cpu_usage,
    processes,
    psutil_stats,
    pytracemalloc,
    start_profiling,
    stop_profiling,
    thread_activity,
)
from w3af.core.controllers.w3af_core import w3afCore

from .profiling_output import (
    environment_variables,
    output_files,
    remove_output_files,
)

ALL_PROFILERS = (
    (core_stats, core_stats.SAVE_THREAD_PTR),
    (cpu_usage, cpu_usage.SAVE_THREAD_PTR),
    (processes, processes.SAVE_PROCESS_PTR),
    (psutil_stats, psutil_stats.SAVE_PSUTIL_PTR),
    (pytracemalloc, pytracemalloc.SAVE_TRACEMALLOC_PTR),
    (thread_activity, thread_activity.SAVE_THREAD_PTR),
)

ALL_FLAGS = {
    "W3AF_CORE_PROFILING": "1",
    "W3AF_CPU_PROFILING": "1",
    "W3AF_PROCESSES": "1",
    "W3AF_PSUTILS": "1",
    "W3AF_PYTRACEMALLOC": "1",
    "W3AF_THREAD_ACTIVITY": "1",
}


class TestProfiling(unittest.TestCase):
    def setUp(self):
        self.remove_all_outputs()

    def tearDown(self):
        for module, save_ptr in ALL_PROFILERS:
            module.cancel_thread(save_ptr)

        yappi.stop()
        yappi.clear_stats()
        tracemalloc.stop()
        self.remove_all_outputs()

    def remove_all_outputs(self):
        for module, _ in ALL_PROFILERS:
            remove_output_files(module.PROFILING_OUTPUT_FMT)

    def test_nothing_is_profiled_by_default(self):
        flags = dict.fromkeys(ALL_FLAGS, "0")
        w3af_core = w3afCore()

        with environment_variables(**flags):
            start_profiling(w3af_core)
            stop_profiling(w3af_core)

        for module, save_ptr in ALL_PROFILERS:
            self.assertEqual(save_ptr, [])
            self.assertEqual(output_files(module.PROFILING_OUTPUT_FMT), [])

    def test_every_profiler_writes_its_output_file(self):
        w3af_core = w3afCore()
        w3af_core.status.start()

        with environment_variables(**ALL_FLAGS):
            start_profiling(w3af_core)

            for module, save_ptr in ALL_PROFILERS:
                self.assertEqual(len(save_ptr), 1, module.__name__)

            self.remove_all_outputs()
            stop_profiling(w3af_core)

        for module, save_ptr in ALL_PROFILERS:
            self.assertEqual(save_ptr, [], module.__name__)
            self.assertEqual(
                len(output_files(module.PROFILING_OUTPUT_FMT)), 1, module.__name__
            )

    def test_stop_profiling_swallows_errors(self):
        with environment_variables(W3AF_CORE_PROFILING="1"):
            stop_profiling(None)

        self.assertEqual(output_files(core_stats.PROFILING_OUTPUT_FMT), [])
