"""
test_core_stats.py

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
import queue
import unittest

import w3af.core.controllers.output_manager as om
from w3af.core.controllers.profiling import core_stats
from w3af.core.controllers.profiling.core_stats import (
    dump_data,
    get_parser_cache_stats,
    get_queue_size,
    start_core_profiling,
    stop_core_profiling,
)
from w3af.core.controllers.w3af_core import w3afCore
from w3af.core.data.parsers import parser_cache
from w3af.core.data.parsers.mp_document_parser import mp_doc_parser

from .profiling_output import (
    environment_variables,
    output_files,
    read_json_output,
    remove_output_files,
)


class TestCoreStats(unittest.TestCase):
    def setUp(self):
        remove_output_files(core_stats.PROFILING_OUTPUT_FMT)

    def tearDown(self):
        core_stats.cancel_thread(core_stats.SAVE_THREAD_PTR)
        mp_doc_parser.stop_workers()
        remove_output_files(core_stats.PROFILING_OUTPUT_FMT)

    def started_core(self):
        w3af_core = w3afCore()
        w3af_core.status.start()
        return w3af_core

    def test_dump_data_of_started_scan_has_all_the_stats(self):
        dump_data(self.started_core(), om.manager)

        data = read_json_output(core_stats.PROFILING_OUTPUT_FMT)
        self.assertNotIn("Exception", data)
        self.assertIn("Requests sent", data)
        self.assertGreaterEqual(data["Requests per minute"], 0)
        self.assertEqual(data["Crawl input queue size"], 0)
        self.assertEqual(data["Audit input queue size"], 0)
        self.assertIn(data["Output manager input queue size"], (0, None))
        self.assertIn("hit_rate", data["Cache stats"])

    def test_dump_data_of_not_started_scan_saves_the_exception(self):
        dump_data(w3afCore(), om.manager)

        data = read_json_output(core_stats.PROFILING_OUTPUT_FMT)
        self.assertIn("get_run_time before start", data["Exception"])
        self.assertIn("RuntimeError", "".join(data["Traceback"]))

    def test_parser_cache_stats_without_parser_pool(self):
        stats = get_parser_cache_stats()

        self.assertEqual(stats["Parser pool worker size"], 0)
        self.assertEqual(stats["Parser pool input queue size"], 0)
        self.assertEqual(stats["max_lru_items"], parser_cache.dpc.get_max_lru_items())

    def test_parser_cache_stats_with_parser_pool(self):
        mp_doc_parser.start_workers()

        stats = get_parser_cache_stats()

        self.assertGreater(stats["Parser pool worker size"], 0)
        self.assertIn(stats["Parser pool input queue size"], (0, None))

    def test_get_queue_size_of_thread_queue(self):
        thread_queue = queue.Queue()
        thread_queue.put("item")

        self.assertEqual(get_queue_size(thread_queue), 1)

    def test_get_queue_size_of_multiprocessing_queue(self):
        # Where the platform has no sem_getvalue() (macOS) the size is unknown
        process_queue = multiprocessing.Queue()

        self.assertIn(get_queue_size(process_queue), (0, None))
        process_queue.close()
        process_queue.join_thread()

    def test_profiling_disabled_does_nothing(self):
        with environment_variables(W3AF_CORE_PROFILING="0"):
            start_core_profiling(self.started_core(), om.manager)
            stop_core_profiling(self.started_core(), om.manager)

        self.assertEqual(core_stats.SAVE_THREAD_PTR, [])
        self.assertEqual(output_files(core_stats.PROFILING_OUTPUT_FMT), [])

    def test_profiling_enabled_dumps_on_start_and_stop(self):
        w3af_core = self.started_core()

        with environment_variables(W3AF_CORE_PROFILING="1"):
            start_core_profiling(w3af_core, om.manager)

            self.assertEqual(len(core_stats.SAVE_THREAD_PTR), 1)
            self.assertEqual(len(output_files(core_stats.PROFILING_OUTPUT_FMT)), 1)

            remove_output_files(core_stats.PROFILING_OUTPUT_FMT)
            stop_core_profiling(w3af_core, om.manager)

        self.assertEqual(core_stats.SAVE_THREAD_PTR, [])
        data = read_json_output(core_stats.PROFILING_OUTPUT_FMT)
        self.assertIn("Requests sent", data)
