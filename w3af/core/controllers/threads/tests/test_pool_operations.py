"""
test_pool_operations.py

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

import itertools
import os
import threading
import time
import unittest

from w3af.core.controllers.threads.decorators import apply_with_return_error
from w3af.core.controllers.threads.threadpool import Pool, one_to_many, return_args

WAIT_TIMEOUT = 10


def square(number):
    return number * number


def fail_on_odd(number):
    if number % 2:
        raise ValueError(f"odd {number}")
    return number


def items_then_error(count):
    yield from range(count)
    raise KeyError("broken iterable")


def slow_items():
    for item in itertools.count():
        time.sleep(0.01)
        yield item


class TestPoolOperations(unittest.TestCase):

    def new_pool(self, processes=2, **kwargs):
        pool = Pool(processes, worker_names="TestWorker", **kwargs)
        self.addCleanup(pool.terminate_join)
        return pool

    def test_map_keeps_order(self):
        pool = self.new_pool()
        self.assertEqual(pool.map(square, range(10)), [n * n for n in range(10)])

    def test_map_with_chunksize(self):
        pool = self.new_pool()
        self.assertEqual(
            pool.map(square, range(7), chunksize=3), [n * n for n in range(7)]
        )

    def test_map_consumes_generators(self):
        pool = self.new_pool()
        self.assertEqual(pool.map(square, (n for n in range(3))), [0, 1, 4])

    def test_map_empty_iterable(self):
        pool = self.new_pool()
        self.assertEqual(pool.map(square, []), [])

    def test_map_raises_the_first_error(self):
        pool = self.new_pool()
        with self.assertRaisesRegex(ValueError, "odd"):
            pool.map(fail_on_odd, range(6), chunksize=1)

    def test_map_multi_args(self):
        pool = self.new_pool()
        self.assertEqual(pool.map_multi_args(pow, [(2, 3), (3, 2)]), [8, 9])

    def test_apply(self):
        pool = self.new_pool()
        self.assertEqual(pool.apply(square, (4,)), 16)

    def test_apply_async_callback_receives_successful_results(self):
        pool = self.new_pool()
        received = []

        pool.apply_async(square, (5,), callback=received.append).get()
        failed = pool.apply_async(fail_on_odd, (1,), callback=received.append)

        self.assertRaises(ValueError, failed.get)
        self.assertEqual(received, [25])

    def test_apply_with_return_error(self):
        pool = self.new_pool()
        self.assertEqual(pool.apply(apply_with_return_error, ((square, 3),)), 9)

    def test_imap_unordered(self):
        pool = self.new_pool()
        self.assertEqual(
            sorted(pool.imap_unordered(square, range(5))), [0, 1, 4, 9, 16]
        )

    def test_imap_unordered_empty_iterable(self):
        pool = self.new_pool()
        self.assertEqual(list(pool.imap_unordered(square, [])), [])

    def test_imap_unordered_iterable_error(self):
        pool = self.new_pool()
        results = pool.imap_unordered(square, items_then_error(3))

        with self.assertRaisesRegex(KeyError, "broken iterable"):
            list(results)

    def test_imap_unordered_iterable_error_on_first_item(self):
        pool = self.new_pool()
        results = pool.imap_unordered(square, items_then_error(0))

        with self.assertRaisesRegex(KeyError, "broken iterable"):
            next(results)

        self.assertEqual(list(results), [])

    def test_imap_unordered_discards_pending_results_after_error(self):
        pool = self.new_pool()

        def fail_after_first_result(number):
            if number == 0:
                raise ValueError("result failed")
            return number

        results = pool.imap_unordered(fail_after_first_result, range(100))

        with self.assertRaisesRegex(ValueError, "result failed"):
            list(results)

        self.assertNotIn(results.job, pool._cache)
        self.assertEqual(len(results._items), 0)

    def test_one_to_many_and_return_args(self):
        pool = self.new_pool()
        func = return_args(one_to_many(pow))
        results = sorted(pool.imap_unordered(func, [(2, 2), (2, 3)]))
        self.assertEqual(results, [(((2, 2),), 4), (((2, 3),), 8)])

    def test_closed_pool_rejects_tasks(self):
        pool = self.new_pool()
        pool.close()

        self.assertTrue(pool.is_closed())
        self.assertFalse(pool.is_running())
        self.assertRaises(RuntimeError, pool.apply_async, square, (1,))
        self.assertRaises(RuntimeError, pool.map_multi_args, pow, [(1, 1)])

    def test_join_requires_close(self):
        pool = self.new_pool()
        self.assertFalse(pool.is_closed())
        self.assertRaises(RuntimeError, pool.join)

    def test_internal_thread_state(self):
        pool = Pool(1)
        alive = {"worker_handler": True, "task_handler": True, "result_handler": True}
        self.assertEqual(pool.get_internal_thread_state(), alive)

        pool.terminate_join()

        dead = dict.fromkeys(alive, False)
        self.assertEqual(pool.get_internal_thread_state(), dead)

    def test_terminate_stops_task_generation(self):
        pool = Pool(1)
        results = pool.imap_unordered(square, slow_items())
        self.assertEqual(next(results), 0)

        pool.terminate_join()

        self.assertFalse(pool.get_internal_thread_state()["task_handler"])

    def test_finish_waits_for_queued_tasks(self):
        pool = Pool(1)
        finished = []

        def slow_task(number):
            time.sleep(0.2)
            finished.append(number)

        for number in range(3):
            pool.apply_async(slow_task, (number,))

        pool.finish(timeout=WAIT_TIMEOUT)

        self.assertTrue(pool.is_closed())
        self.assertEqual(finished, [0, 1, 2])

    def test_default_process_count(self):
        pool = Pool()
        self.addCleanup(pool.terminate_join)
        self.assertEqual(pool.get_worker_count(), os.cpu_count() or 1)

    def test_initializer(self):
        initialized = []
        pool = self.new_pool(1, initializer=initialized.append, initargs=("ready",))
        pool.apply(square, (1,))
        self.assertEqual(initialized, ["ready"])

    def test_invalid_arguments(self):
        self.assertRaises(ValueError, Pool, 0)
        self.assertRaises(TypeError, Pool, 1, initializer="not callable")
        self.assertRaises(ValueError, Pool, 1, maxtasksperchild=0)
        self.assertRaises(ValueError, Pool, 1, max_queued_tasks=1)

    def test_set_worker_count_requires_positive_count(self):
        pool = self.new_pool(maxtasksperchild=3)
        self.assertRaises(ValueError, pool.set_worker_count, 0)

    def test_queues(self):
        pool = self.new_pool()
        self.assertEqual(pool.get_inqueue().qsize(), 0)
        self.assertEqual(pool.get_outqueue().qsize(), 0)


class TestRunningTaskInspection(unittest.TestCase):
    """
    Inspect what a worker is running while the task waits for an event
    """

    def setUp(self):
        self.started = threading.Event()
        self.release = threading.Event()
        self.pool = Pool(1, worker_names="TestWorker")
        self.addCleanup(self.pool.terminate_join)
        self.addCleanup(self.release.set)

    def blocking_task(self, *args):
        self.started.set()
        self.release.wait(WAIT_TIMEOUT)
        return args

    def running_state(self, func, args):
        result = self.pool.apply_async(func, args)
        self.assertTrue(self.started.wait(WAIT_TIMEOUT))

        state = self.pool.inspect_threads()[0]
        running_tasks = self.pool.get_running_task_count()

        self.release.set()
        result.get()
        return state, running_tasks

    def test_plain_function(self):
        state, running_tasks = self.running_state(self.blocking_task, (1,))

        self.assertEqual(state["func_name"], "blocking_task")
        self.assertEqual(state["args"], (1,))
        self.assertFalse(state["idle"])
        self.assertEqual(state["name"], "TestWorker")
        self.assertEqual(running_tasks, 1)

    def test_mapstar(self):
        result = self.pool.map_async(self.blocking_task, [7])
        self.assertTrue(self.started.wait(WAIT_TIMEOUT))

        state = self.pool.inspect_threads()[0]

        self.release.set()
        self.assertEqual(result.get(), [(7,)])
        self.assertEqual(state["func_name"], "blocking_task")
        self.assertEqual(state["args"], ((7,),))

    def test_apply_with_return_error(self):
        args = ((self.blocking_task, 2),)
        state, _ = self.running_state(apply_with_return_error, args)

        self.assertEqual(state["func_name"], "blocking_task")
        self.assertEqual(state["args"], (2,))

    def test_return_args(self):
        state, _ = self.running_state(return_args(self.blocking_task), (3,))

        self.assertEqual(state["func_name"], "blocking_task")
        self.assertEqual(state["args"], (3,))

    def test_one_to_many(self):
        state, _ = self.running_state(one_to_many(self.blocking_task), ((4, 5),))

        self.assertEqual(state["func_name"], "blocking_task")
        self.assertEqual(state["args"], ((4, 5),))

    def test_idle_worker(self):
        state = self.pool.inspect_threads()[0]

        self.assertTrue(state["idle"])
        self.assertIsNone(state["func_name"])
        self.assertEqual(self.pool.get_running_task_count(), 0)
