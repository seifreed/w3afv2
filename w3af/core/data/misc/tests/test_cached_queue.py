"""
test_cached_queue.py

Copyright 2017 Andres Riancho

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

import queue
import threading
import time
import unittest

from w3af.core.data.misc.cached_queue import CachedQueue


class TestCachedQueue(unittest.TestCase):

    def test_prefer_memory_over_disk(self):
        q = CachedQueue(maxsize=2)

        # These two go to the in memory queue
        q.put(1)
        q.put(2)

        # This one goes to the disk queue
        q.put(3)

        # Read one from memory
        q.get()
        self.assertEqual(len(q.memory), 1)
        self.assertEqual(len(q.disk), 1)

        # Write one to memory
        q.put(4)
        self.assertEqual(len(q.memory), 2)
        self.assertEqual(len(q.disk), 1)

    def test_add_exceed_memory(self):
        q = CachedQueue(maxsize=2)

        # These two go to the in memory queue
        q.put(1)
        q.put(2)

        self.assertEqual(q.qsize(), 2)
        self.assertEqual(len(q.memory), 2)

        # This one goes to the disk queue
        q.put(3)

        self.assertEqual(q.qsize(), 3)
        self.assertEqual(len(q.memory), 2)
        self.assertEqual(len(q.disk), 1)

        # Get all
        self.assertEqual(q.get(), 1)

        self.assertEqual(len(q.memory), 1)
        self.assertEqual(len(q.disk), 1)

        self.assertEqual(q.get(), 2)

        self.assertEqual(len(q.memory), 0)
        self.assertEqual(len(q.disk), 1)

        self.assertEqual(q.get(), 3)

        self.assertEqual(len(q.memory), 0)
        self.assertEqual(len(q.disk), 0)

        self.assertEqual(q.qsize(), 0)

    def test_exceptions_no_fail_sync_pointer(self):
        q = CachedQueue(maxsize=2)
        q.put(1)
        q.get()

        self.assertRaises(queue.Empty, q.get, block=False)

        q.put(1)
        self.assertEqual(q.get(), 1)

    def test_dict_items_spilled_to_disk(self):
        q = CachedQueue(maxsize=1)
        q.put({"in": "memory"})
        q.put({"on": "disk"})

        self.assertEqual(len(q.disk), 1)
        self.assertEqual(q.get(), {"in": "memory"})
        self.assertEqual(q.get(), {"on": "disk"})

    def test_name_and_processed_tasks(self):
        q = CachedQueue(maxsize=1, name="audit")
        q.put("a")
        q.put("b")
        q.get()
        q.get()

        self.assertEqual(q.get_name(), "audit")
        self.assertEqual(q.get_processed_tasks(), 2)

    def test_simple_rpm_speed(self):
        q = CachedQueue()

        self.assertEqual(0.0, q.get_input_rpm())
        self.assertEqual(0.0, q.get_output_rpm())

        for i in range(4):
            q.put(i)

        self.assertEqual(q.qsize(), 4)
        self.assertEqual(len(q._input_timestamps), 4)
        self.assertGreater(q.get_input_rpm(), 0)

        for _ in range(4):
            q.get()

        self.assertEqual(q.qsize(), 0)
        self.assertEqual(len(q._output_timestamps), 4)
        self.assertGreater(q.get_output_rpm(), 0)

    def test_join_memory(self):
        q = CachedQueue(maxsize=2)
        q.put(1)

        def queue_get_after_delay(queue):
            time.sleep(1)
            queue.get()
            queue.task_done()

        t = threading.Thread(target=queue_get_after_delay, args=(q,))
        t.start()

        start = time.time()

        # This should take 1 second
        q.join()

        spent = time.time() - start

        self.assertGreater(spent, 1)

    def test_join_memory_and_disk(self):
        q = CachedQueue(maxsize=2)
        for x in range(10):
            q.put(x)

        def queue_get_after_delay(queue):
            time.sleep(1)

            for x in range(2):
                queue.get()
                queue.task_done()

            time.sleep(1)

            for x in range(8):
                queue.get()
                queue.task_done()

        t = threading.Thread(target=queue_get_after_delay, args=(q,))
        t.start()

        start = time.time()

        # This should take 3 seconds
        q.join()

        spent = time.time() - start

        self.assertGreater(spent, 2)

    def test_join_logs_when_a_wait_times_out(self):
        q = CachedQueue(maxsize=2, name="timeout_test")
        q.put(1)

        def consume_after_timeout(queue):
            time.sleep(5.1)
            queue.get()
            queue.task_done()

        consumer = threading.Thread(target=consume_after_timeout, args=(q,))
        consumer.start()

        with self.assertLogs("w3af.core.data.misc.cached_queue", level="DEBUG") as logs:
            q.join()

        consumer.join()
        self.assertTrue(
            any("Still have 1 unfinished tasks" in record for record in logs.output)
        )
