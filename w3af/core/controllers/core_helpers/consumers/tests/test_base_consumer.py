"""
test_base_consumer.py

Copyright 2011 Andres Riancho

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

import w3af.core.controllers.output_manager as om
from w3af.core.constants import POISON_PILL
from w3af.core.controllers.core_helpers.consumers.base_consumer import BaseConsumer
from w3af.core.controllers.core_helpers.consumers.tests.consumer_plugins import (
    WAIT_TIMEOUT,
    wait_until,
)
from w3af.core.controllers.tests.recording_output import (
    recording_output,
    start_recording_output,
)
from w3af.core.controllers.w3af_core import w3afCore
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.request.fuzzable_request import FuzzableRequest


class TeardownCountingConsumer(BaseConsumer):
    """
    A consumer whose teardown counts how many times the consumer loop asked
    for it and whose _consume records the work units it received.
    """

    def __init__(self, w3af_core, create_pool=True, thread_pool_size=None):
        super().__init__(
            [],
            w3af_core,
            "TestConsumer",
            create_pool=create_pool,
            thread_pool_size=thread_pool_size,
            output=om.out,
        )
        self.teardown_calls = 0
        self.consumed = []

    def get_name(self):
        return "TestConsumer"

    def _teardown(self):
        self.teardown_calls += 1

    def _consume(self, work_unit):
        if isinstance(work_unit, Exception):
            raise work_unit
        self.consumed.append(work_unit)


class FailingTeardownConsumer(TeardownCountingConsumer):
    def _teardown(self):
        raise ValueError("teardown failed")


class NamelessFailingTeardownConsumer(BaseConsumer):
    """
    A consumer which does not implement get_name() and whose teardown fails,
    the error reporting in _call_teardown() then fails too.
    """

    def __init__(self, w3af_core):
        super().__init__([], w3af_core, "Nameless", create_pool=False, output=om.out)

    def _teardown(self):
        raise ValueError("teardown failed")


class TestBaseConsumer(unittest.TestCase):

    def setUp(self):
        self.core = w3afCore()
        self.bc = TeardownCountingConsumer(self.core)

    def tearDown(self):
        self.bc._shutdown_threadpool()
        self.core.quit()

    def test_handle_exception(self):
        url = URL("http://127.0.0.1/")
        fr = FuzzableRequest(url)

        raised = ValueError()

        try:
            raise raised
        except ValueError as e:
            self.bc.handle_exception("audit", "sqli", fr, e)

        exception_data = self.bc.out_queue.get()

        self.assertTrue(exception_data.traceback_str is not None)
        self.assertEqual(exception_data.phase, "audit")
        self.assertEqual(exception_data.plugin, "sqli")
        self.assertEqual(exception_data.exception, raised)

    def test_queues_use_core_database(self):
        self.assertIs(self.bc.in_queue.disk.db, self.core.database)
        self.assertIs(self.bc.out_queue.disk.db, self.core.database)

    def test_terminate(self):
        self.bc.start()
        self.bc.terminate()

        self.assertEqual(self.bc.teardown_calls, 1)
        self.assertTrue(self.bc.has_finished())
        self.assertEqual(self.bc.get_result_nowait(), POISON_PILL)

    def test_terminate_terminate(self):
        self.bc.start()
        self.bc.terminate()
        self.bc.terminate()

        self.assertEqual(self.bc.teardown_calls, 1)

    def test_consumes_work_until_poison_pill(self):
        recorder = start_recording_output()
        self.bc.start()

        self.bc.in_queue_put_iter(["a", "b"])
        self.bc.in_queue_put_iter(None)
        self.bc.in_queue_put(None)
        self.bc.join()

        self.assertEqual(self.bc.consumed, ["a", "b"])
        self.assertEqual(self.bc.get_result(), POISON_PILL)
        self.assertIn(
            "TestConsumer pool has been joined", recorder.messages_of("debug")
        )

    def test_work_is_ignored_after_poison_pill(self):
        self.bc.send_poison_pill()
        self.bc.send_poison_pill()

        self.assertIsNone(self.bc.in_queue_put("ignored"))
        self.assertEqual(self.bc.in_queue_size(), 1)

    def test_consume_wrapper_marks_failed_task_as_done(self):
        error = ValueError("consume failed")

        with self.assertRaises(ValueError):
            self.bc._consume_wrapper(error)

        self.assertFalse(self.bc.has_pending_work())

    def test_task_done_for_unknown_task(self):
        with self.assertRaises(AssertionError):
            self.bc._task_done("unknown")

    def test_get_pool(self):
        self.assertIs(self.bc.get_pool(), self.bc._threadpool)

    def test_get_running_task_count(self):
        self.assertEqual(self.bc.get_running_task_count(), 0)

        self.bc._shutdown_threadpool()

        self.assertEqual(self.bc.get_running_task_count(), 0)

    def test_shutdown_without_pool(self):
        recorder = start_recording_output()
        consumer = TeardownCountingConsumer(self.core, create_pool=False)

        consumer._shutdown_threadpool()

        self.assertIn(
            "TestConsumer pool is None. No shutdown required.",
            recorder.messages_of("debug"),
        )

    def test_add_observer(self):
        observer = object()

        self.bc.add_observer(observer)

        self.assertEqual(self.bc._observers, [observer])

    def test_log_queue_sizes_after_poison_pill(self):
        recorder = start_recording_output()
        self.bc._log_queue_sizes()
        self.assertEqual(recorder.messages_of("debug"), [])

        self.bc.send_poison_pill()
        self.bc._add_task("pending")
        self.bc._log_queue_sizes()

        debug_messages = recorder.messages_of("debug")
        self.assertIn(
            "The TestConsumer consumer has 1 tasks in progress", debug_messages
        )
        self.assertIn(
            "The TestConsumer consumer pool has 0 tasks in the input queue"
            " and 0 tasks in the output queue",
            debug_messages,
        )

    def test_teardown_error_is_logged(self):
        recorder = start_recording_output()
        consumer = FailingTeardownConsumer(self.core, create_pool=False)
        consumer.start()

        consumer.join()

        self.assertTrue(consumer.has_finished())
        self.assertIn(
            "Exception found while calling teardown() in TestConsumer consumer:"
            ' "teardown failed"',
            recorder.messages_of("debug"),
        )

    def test_terminate_clears_queues_of_stopped_consumer(self):
        self.bc.in_queue_put("in")
        self.bc.out_queue.put("out")

        self.bc.terminate()

        self.assertEqual(self.bc.in_queue_size(), 0)
        self.assertEqual(self.bc.out_queue.qsize(), 0)
        self.assertEqual(self.bc.consumed, [])


class TestPendingWork(unittest.TestCase):

    def setUp(self):
        self.core = w3afCore()
        self.bc = TeardownCountingConsumer(self.core, thread_pool_size=1)
        self.release = threading.Event()

    def tearDown(self):
        self.release.set()
        self.bc._shutdown_threadpool()
        self.core.quit()

    def blocked_task(self, *args):
        self.release.wait(WAIT_TIMEOUT)

    def test_no_pending_work(self):
        self.assertFalse(self.bc.has_pending_work())

    def test_pending_work_in_input_queue(self):
        self.bc.in_queue_put("work")
        self.assertTrue(self.bc.has_pending_work())

    def test_pending_work_in_output_queue(self):
        self.bc.out_queue.put("result")
        self.assertTrue(self.bc.has_pending_work())

    def test_pending_work_in_progress(self):
        self.bc._add_task("running")
        self.assertTrue(self.bc.has_pending_work())

    def test_pending_work_in_pool_input_queue(self):
        pool = self.bc.get_pool()
        pool.apply_async(self.blocked_task)
        pool.apply_async(self.blocked_task)

        wait_until(lambda: pool._inqueue.qsize() > 0)

        self.assertTrue(self.bc.has_pending_work())

    def test_pending_work_in_pool_output_queue(self):
        pool = self.bc.get_pool()
        pool.apply_async(int, callback=self.blocked_task)
        pool.apply_async(int)

        wait_until(lambda: pool._outqueue.qsize() > 0)

        self.assertTrue(self.bc.has_pending_work())


class TestAbstractConsumer(unittest.TestCase):

    def setUp(self):
        self.core = w3afCore()

    def tearDown(self):
        self.core.quit()

    def test_abstract_methods(self):
        consumer = BaseConsumer(
            [], self.core, "Abstract", create_pool=False, output=om.out
        )

        self.assertRaises(NotImplementedError, consumer.get_name)
        self.assertRaises(NotImplementedError, consumer._teardown)
        self.assertRaises(NotImplementedError, consumer._consume, None)

    def test_output_sink_is_injected(self):
        output = recording_output()
        consumer = BaseConsumer(
            [], self.core, "InjectedOutput", create_pool=False, output=output
        )

        self.assertIs(consumer._output, output)

    def test_poison_pill_error_is_logged(self):
        recorder = start_recording_output()
        consumer = NamelessFailingTeardownConsumer(self.core)
        consumer.start()

        consumer.join()

        self.assertTrue(consumer.has_finished())
        self.assertEqual(consumer.get_result(), POISON_PILL)
        self.assertIn(
            'An exception was found while processing poison pill: ""',
            recorder.messages_of("debug"),
        )
