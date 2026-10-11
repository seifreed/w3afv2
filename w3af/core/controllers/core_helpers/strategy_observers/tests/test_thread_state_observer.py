"""
test_thread_state_observer.py

Copyright 2018 Andres Riancho

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
import time
import unittest

import w3af.core.controllers.output_manager as om
from w3af.core.controllers.core_helpers.consumers.audit import audit
from w3af.core.controllers.core_helpers.consumers.crawl_infrastructure import (
    CrawlInfrastructure,
)
from w3af.core.controllers.core_helpers.consumers.grep import grep
from w3af.core.controllers.core_helpers.strategy_observers.thread_state_observer import (
    ThreadStateObserver,
)
from w3af.core.controllers.tests.recording_output import start_recording_output
from w3af.core.controllers.threads.threadpool import Pool
from w3af.core.controllers.w3af_core import w3afCore
from w3af.core.data.kb.knowledge_base import DBKnowledgeBase
from w3af.plugins.grep.private_ip import private_ip

WAIT_TIMEOUT = 10

DISCOVER_WORKER_REPR = (
    "<bound method CrawlInfrastructure._discover_worker of"
    " <CrawlInfrastructure(CrawlInfraController, started daemon 1234)>>"
)


class QuickThreadStateObserver(ThreadStateObserver):
    ANALYZE_EVERY = 0
    POLL_INTERVAL = 0.05
    STACK_TRACE_MIN_TIME = 0


def record_output(test_case):
    recorder = start_recording_output()
    test_case.addCleanup(om.manager.get_output_plugin_inst().remove, recorder)
    return recorder


def wait_for_message(recorder, text):
    deadline = time.time() + WAIT_TIMEOUT

    while time.time() < deadline:
        if any(text in message for message in recorder.messages_of("debug")):
            return True
        time.sleep(0.05)

    return False


def alive_threads_named(name):
    return [thread for thread in threading.enumerate() if thread.name == name]


def worker_state(**overrides):
    state: dict[str, object] = {
        "func_name": "audit_plugin",
        "args": (),
        "kwargs": {},
        "start_time": None,
        "idle": True,
        "job": 1,
        "worker_id": "abc123",
        "name": "WorkerThread",
    }
    state.update(overrides)
    return state


class TestInspectDataToLog(unittest.TestCase):
    def setUp(self):
        self.pool = Pool(processes=1, worker_names="WorkerThread")
        self.addCleanup(self.pool.terminate_join)
        self.observer = ThreadStateObserver(om.out)
        self.recorder = record_output(self)

    def debug_messages(self):
        """
        :return: The debug messages, without the ones about the time it took
                 the output manager to flush the output plugins
        """
        return [
            message
            for message in self.recorder.messages_of("debug")
            if ".flush() took" not in message
        ]

    def test_inspect_data_to_log(self):
        def sleep(sleep_time, **kwargs):
            time.sleep(sleep_time)

        self.pool.apply_async(func=sleep, args=(2,), kwds={"x": 2})

        # Let the worker get the task
        time.sleep(0.3)

        worker_states = self.pool.inspect_threads()

        # inspect_data_to_log only writes the detailed line for workers that
        # have been running for at least 10 seconds. Backdate the running
        # worker's start time so the detailed line is produced without the test
        # having to wait that long.
        for state in worker_states:
            if not state["idle"]:
                state["start_time"] = time.time() - 11

        self.observer.inspect_data_to_log(self.pool, worker_states)

        messages = self.debug_messages()
        self.assertEqual(len(messages), 2, messages)

        message_re = (
            "Worker with ID .*? has been running job .*? for .*? seconds."
            " The job is: sleep\\(2, kwargs={'x': '2'}\\)"
        )
        self.assertRegex(messages[0], message_re)
        self.assertEqual(messages[1], "0% of WorkerThread workers are idle.")

    def test_no_workers(self):
        self.observer.inspect_data_to_log(self.pool, [])

        self.assertEqual(self.debug_messages(), ["No pool workers at WorkerThread."])

    def test_idle_and_recently_started_workers(self):
        inspect_data = [
            worker_state(worker_id="idle1"),
            worker_state(worker_id="new1", idle=False, start_time=time.time()),
            worker_state(worker_id="unknown1", idle=False),
        ]

        self.observer.inspect_data_to_log(self.pool, inspect_data)

        self.assertEqual(
            self.debug_messages(),
            [
                "Worker with ID WorkerThread(idle1) is idle.",
                "33% of WorkerThread workers are idle.",
            ],
        )

    def test_long_arguments_trace_and_discover_worker(self):
        state = worker_state(
            func_name=DISCOVER_WORKER_REPR,
            args=("A" * 100,),
            kwargs={"debugging_id": "B" * 100},
            idle=False,
            start_time=time.time() - 30,
            trace="threading.py:1 @ run()",
        )

        self.observer.inspect_data_to_log(self.pool, [state])

        message = self.debug_messages()[0]
        truncated_arg = "'" + "A" * 79 + "...'"
        truncated_kwarg = "'" + "B" * 79 + "...'"

        self.assertIn(f"The job is: _discover_worker({truncated_arg}", message)
        self.assertIn(truncated_kwarg, message)
        self.assertTrue(
            message.endswith(". Function call tree: threading.py:1 @ run()")
        )

    def test_clean_function_name(self):
        self.assertEqual(
            self.observer.clean_function_name(DISCOVER_WORKER_REPR), "_discover_worker"
        )
        self.assertEqual(self.observer.clean_function_name("audit"), "audit")


class TestAddThreadStack(unittest.TestCase):
    def setUp(self):
        self.pool = Pool(processes=2, worker_names="StackWorker")
        self.addCleanup(self.pool.terminate_join)

    def test_without_long_running_workers(self):
        inspect_data = self.pool.inspect_threads()

        result = ThreadStateObserver(om.out).add_thread_stack(inspect_data)

        self.assertIs(result, inspect_data)
        self.assertTrue(all("trace" not in state for state in result))

    def test_adds_the_stack_of_long_running_workers(self):
        started = threading.Event()
        release = threading.Event()
        self.addCleanup(release.set)

        def wait_for_release():
            started.set()
            release.wait(WAIT_TIMEOUT)

        self.pool.apply_async(func=wait_for_release)
        started.wait(WAIT_TIMEOUT)

        inspect_data = QuickThreadStateObserver(om.out).add_thread_stack(
            self.pool.inspect_threads()
        )

        running = [state for state in inspect_data if not state["idle"]]
        idle = [state for state in inspect_data if state["idle"]]

        self.assertEqual(len(running), 1)
        self.assertEqual(len(idle), 1)
        self.assertIn("@ wait_for_release()", running[0]["trace"])
        self.assertNotIn("trace", idle[0])


class TestPoolStateThreads(unittest.TestCase):
    def setUp(self):
        self.w3af_core = w3afCore()
        self.addCleanup(self.w3af_core.worker_pool.terminate_join)
        self.observer = QuickThreadStateObserver(om.out)
        self.addCleanup(self.observer.end)
        self.recorder = record_output(self)

    def close_pool_on_cleanup(self, consumer):
        self.addCleanup(consumer.get_pool().terminate_join)
        return consumer

    def assert_logged(self, text):
        self.assertTrue(wait_for_message(self.recorder, text), text)

    def test_audit(self):
        consumer = self.close_pool_on_cleanup(
            audit([], self.w3af_core, om.out, self.w3af_core.configuration)
        )

        self.observer.audit(consumer)
        self.observer.audit(consumer)

        self.assert_logged("AuditorWorker worker pool has 0 tasks in inqueue")
        self.assert_logged("AuditorWorker worker pool internal thread state")
        self.assertEqual(len(alive_threads_named("AuditPoolStateObserver")), 1)

        self.observer.end()

        self.assertEqual(alive_threads_named("AuditPoolStateObserver"), [])

    def test_grep(self):
        consumer = self.close_pool_on_cleanup(
            grep(
                [private_ip()],
                self.w3af_core,
                om.out,
                self.w3af_core.configuration,
            )
        )

        self.observer.grep(consumer)

        self.assert_logged("GrepWorker worker pool has 0 tasks in inqueue")

    def test_crawl(self):
        consumer = self.close_pool_on_cleanup(
            CrawlInfrastructure(
                [],
                self.w3af_core,
                60,
                knowledge_base=kb,
                output=om.out,
                configuration=self.w3af_core.configuration,
            )
        )

        self.observer.crawl(consumer)
        self.observer.crawl(consumer)

        self.assert_logged("CrawlInfraWorker worker pool has 0 tasks in inqueue")
        self.assert_logged("Worker worker pool internal thread state")
        self.assertEqual(len(alive_threads_named("WorkerPoolStateObserver")), 1)

    def test_end_without_threads(self):
        ThreadStateObserver(om.out).end()


kb = DBKnowledgeBase()
