"""
test_psutil_stats.py

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

import collections
import multiprocessing
import os
import unittest

import psutil

from w3af.core.controllers.profiling import psutil_stats
from w3af.core.controllers.profiling.psutil_stats import (
    as_plain_data,
    get_human_readable_size,
    get_memory_usage,
    get_process_memory,
    get_processes_info,
    get_threads_cpu_percent,
    start_psutil_dump,
    stop_psutil_dump,
    user_wants_psutil,
)

from .profiling_output import (
    environment_variables,
    output_files,
    read_json_output,
    remove_output_files,
)

Point = collections.namedtuple("Point", ["x", "y"])


class TestPsutilStats(unittest.TestCase):
    def setUp(self):
        remove_output_files(psutil_stats.PROFILING_OUTPUT_FMT)

    def tearDown(self):
        psutil_stats.cancel_thread(psutil_stats.SAVE_PSUTIL_PTR)
        remove_output_files(psutil_stats.PROFILING_OUTPUT_FMT)

    def test_user_wants_psutil(self):
        for value, expected in (
            ("1", True),
            ("0", False),
            ("yes", False),
            ("2", False),
        ):
            with environment_variables(W3AF_PSUTILS=value):
                self.assertEqual(user_wants_psutil(), expected, value)

    def test_as_plain_data_converts_named_tuples(self):
        self.assertEqual(as_plain_data(Point(1, 2)), {"x": 1, "y": 2})

    def test_as_plain_data_keeps_other_values(self):
        self.assertIsNone(as_plain_data(None))
        self.assertEqual(as_plain_data(["a"]), ["a"])

    def test_get_human_readable_size(self):
        cases = (
            (0, "0 B"),
            (1023, "1023 B"),
            (1024, "1 KB"),
            (5 * 1024**2 + 10, "5 MB"),
            (3 * 1024**3, "3 GB"),
            (2 * 1024**4, "2 TB"),
            (7 * 1024**5, "7 PB"),
            (2048 * 1024**5, "2048 PB"),
        )
        for size, expected in cases:
            self.assertEqual(get_human_readable_size(size), expected)

    def test_get_processes_info_has_this_process(self):
        info = get_processes_info()[os.getpid()]

        self.assertEqual(info["pid"], os.getpid())
        self.assertEqual(info["ppid"], os.getppid())
        self.assertIn("python", info["exe"].lower())
        self.assertEqual(info["cmdline"], psutil.Process().cmdline())
        self.assertGreater(info["memory_info"]["rss"], 0)
        self.assertGreaterEqual(info["num_threads"], 1)

    def test_get_memory_usage_includes_children(self):
        release = multiprocessing.Event()
        child = multiprocessing.Process(target=release.wait, args=(60,), daemon=True)
        child.start()

        try:
            usage = get_memory_usage()
        finally:
            release.set()
            child.join(timeout=60)

        self.assertGreaterEqual(len(usage), 2)
        for memory in usage:
            self.assertGreater(memory["RSS"], 0)
            self.assertGreaterEqual(memory["VMS"], memory["RSS"])
            self.assertTrue(memory["Command line"])

    def test_get_process_memory_of_this_process(self):
        memory = get_process_memory(psutil.Process())

        self.assertGreater(memory["RSS"], 0)
        self.assertIn("python", memory["Command line"].lower())

    def test_get_process_memory_of_finished_process_is_none(self):
        release = multiprocessing.Event()
        child = multiprocessing.Process(target=release.wait, args=(60,))
        child.start()
        finished = psutil.Process(child.pid)
        release.set()
        child.join(timeout=60)

        self.assertIsNone(get_process_memory(finished))

    def test_get_threads_cpu_percent_has_every_thread(self):
        result = get_threads_cpu_percent(interval=0.05)

        self.assertEqual(len(result), psutil.Process().num_threads())
        for thread_data in result.values():
            self.assertGreaterEqual(thread_data["Thread total time"], 0)
            self.assertGreaterEqual(thread_data["Thread CPU usage %"], 0)

    def test_profiling_disabled_does_nothing(self):
        with environment_variables(W3AF_PSUTILS="0"):
            start_psutil_dump()
            stop_psutil_dump()

        self.assertEqual(psutil_stats.SAVE_PSUTIL_PTR, [])
        self.assertEqual(output_files(psutil_stats.PROFILING_OUTPUT_FMT), [])

    def test_profiling_enabled_dumps_operating_system_data(self):
        with environment_variables(W3AF_PSUTILS="1"):
            start_psutil_dump()

            self.assertEqual(len(psutil_stats.SAVE_PSUTIL_PTR), 1)

            remove_output_files(psutil_stats.PROFILING_OUTPUT_FMT)
            stop_psutil_dump()

        self.assertEqual(psutil_stats.SAVE_PSUTIL_PTR, [])
        data = read_json_output(psutil_stats.PROFILING_OUTPUT_FMT)
        self.assertGreater(data["Virtual memory"]["total"], 0)
        self.assertIn("user", data["CPU"])
        self.assertEqual(len(data["Load average"]), 3)
        self.assertIn(str(os.getpid()), data["Processes"])
        self.assertGreaterEqual(len(data["Process memory"]), 1)
        self.assertEqual(set(data["Disk usage"]), {"total", "free", "% used"})
        self.assertGreaterEqual(len(data["Thread CPU usage"]), 1)
        self.assertIn("Network", data)
        self.assertIn("Swap memory", data)
        self.assertIn("Disk IO counters", data)
