"""
test_pytracemalloc.py

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

from w3af.core.controllers.profiling import pytracemalloc
from w3af.core.controllers.profiling.pytracemalloc import (
    start_tracemalloc_dump,
    stop_tracemalloc_dump,
)
from w3af.core.data.misc.serialize import load

from .profiling_output import (
    environment_variables,
    latest_output_file,
    output_files,
    remove_output_files,
)


class TestPyTraceMalloc(unittest.TestCase):
    def setUp(self):
        remove_output_files(pytracemalloc.PROFILING_OUTPUT_FMT)

    def tearDown(self):
        pytracemalloc.cancel_thread(pytracemalloc.SAVE_TRACEMALLOC_PTR)
        tracemalloc.stop()
        remove_output_files(pytracemalloc.PROFILING_OUTPUT_FMT)

    def test_profiling_disabled_does_nothing(self):
        with environment_variables(W3AF_PYTRACEMALLOC="0"):
            start_tracemalloc_dump()
            stop_tracemalloc_dump()

        self.assertFalse(tracemalloc.is_tracing())
        self.assertEqual(pytracemalloc.SAVE_TRACEMALLOC_PTR, [])
        self.assertEqual(output_files(pytracemalloc.PROFILING_OUTPUT_FMT), [])

    def test_profiling_enabled_saves_snapshot_with_allocations(self):
        with environment_variables(W3AF_PYTRACEMALLOC="1"):
            start_tracemalloc_dump()

            self.assertTrue(tracemalloc.is_tracing())
            self.assertEqual(tracemalloc.get_traceback_limit(), 25)
            self.assertEqual(len(pytracemalloc.SAVE_TRACEMALLOC_PTR), 1)

            retained = [str(i) * 10 for i in range(5000)]
            stop_tracemalloc_dump()

        self.assertEqual(pytracemalloc.SAVE_TRACEMALLOC_PTR, [])
        with open(latest_output_file(pytracemalloc.PROFILING_OUTPUT_FMT), "rb") as fh:
            snapshot = load(fh)

        self.assertIsInstance(snapshot, tracemalloc.Snapshot)
        filenames = {
            stat.traceback[0].filename for stat in snapshot.statistics("filename")
        }
        self.assertIn(__file__, filenames)
        self.assertEqual(len(retained), 5000)
