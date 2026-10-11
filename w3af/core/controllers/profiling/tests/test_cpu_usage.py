"""
test_cpu_usage.py

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

import hashlib
import pstats
import unittest
from typing import Protocol, cast

import yappi

from w3af.core.controllers.profiling import cpu_usage
from w3af.core.controllers.profiling.cpu_usage import (
    start_cpu_profiling,
    stop_cpu_profiling,
)

from .profiling_output import (
    environment_variables,
    latest_output_file,
    output_files,
    remove_output_files,
)


class YappiApi(Protocol):
    def stop(self) -> None: ...

    def clear_stats(self) -> None: ...

    def is_running(self) -> bool: ...


yappi_api = cast(YappiApi, yappi)


def hash_some_data():
    for i in range(2000):
        hashlib.sha256(str(i).encode()).hexdigest()


class TestCpuUsage(unittest.TestCase):
    def setUp(self):
        remove_output_files(cpu_usage.PROFILING_OUTPUT_FMT)

    def tearDown(self):
        cpu_usage.cancel_thread(cpu_usage.SAVE_THREAD_PTR)
        yappi_api.stop()
        yappi_api.clear_stats()
        remove_output_files(cpu_usage.PROFILING_OUTPUT_FMT)

    def test_profiling_disabled_does_nothing(self):
        with environment_variables(W3AF_CPU_PROFILING="0"):
            start_cpu_profiling()
            hash_some_data()
            stop_cpu_profiling()

        self.assertFalse(yappi_api.is_running())
        self.assertEqual(cpu_usage.SAVE_THREAD_PTR, [])
        self.assertEqual(output_files(cpu_usage.PROFILING_OUTPUT_FMT), [])

    def test_profiling_enabled_saves_pstat_file_with_profiled_function(self):
        with environment_variables(W3AF_CPU_PROFILING="1"):
            start_cpu_profiling()

            self.assertTrue(yappi_api.is_running())
            self.assertEqual(len(cpu_usage.SAVE_THREAD_PTR), 1)

            hash_some_data()
            stop_cpu_profiling()

        self.assertEqual(cpu_usage.SAVE_THREAD_PTR, [])
        output_file = latest_output_file(cpu_usage.PROFILING_OUTPUT_FMT)
        stats = pstats.Stats(output_file)
        profiled_functions = {
            function_name for (_, _, function_name) in getattr(stats, "stats", ())
        }
        self.assertIn("hash_some_data", profiled_functions)
