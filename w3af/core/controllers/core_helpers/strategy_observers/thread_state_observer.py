"""
thread_state_observer.py

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

import re
import sys
import threading
import time
import traceback

from w3af.core.data.misc.encoding import smart_unicode

from .strategy_observer import StrategyObserver


class ThreadStateObserver(StrategyObserver):
    """
    Monitor number jobs which are running in the different threads.
    """

    ANALYZE_EVERY = 30
    POLL_INTERVAL = 2.0
    STACK_TRACE_MIN_TIME = 120
    MIN_RUNNING_TIME_TO_LOG = 10
    MAX_ARGUMENT_LENGTH = 80
    DISCOVER_WORKER_RE = re.compile(
        "<bound method CrawlInfrastructure._discover_worker"
        r" of <CrawlInfrastructure\(CrawlInfraController,"
        r" started daemon .*?\)>>"
    )

    def __init__(self, output):
        super().__init__()
        self._output = output

        self._stop = threading.Event()
        self._threads_lock = threading.Lock()
        self._threads = {}

    def end(self):
        self._stop.set()

        with self._threads_lock:
            threads = list(self._threads.values())

        for thread in threads:
            thread.join()

    def crawl(self, consumer, *args):
        """
        Log the thread state for crawl infra plugins and the core worker pool

        :param consumer: A crawl consumer instance
        :param args: Fuzzable requests that we don't care about
        :return: None, everything is written to disk
        """
        self._observe_pool_once(
            "CrawlInfraPoolStateObserver", consumer.get_pool, "CrawlInfraWorker"
        )
        self._observe_pool_once(
            "WorkerPoolStateObserver", lambda: consumer._w3af_core.worker_pool, "Worker"
        )

    def audit(self, consumer, *args):
        """
        Log the thread state for audit plugins

        :param consumer: An audit consumer instance
        :param args: Fuzzable requests that we don't care about
        :return: None, everything is written to disk
        """
        self._observe_pool_once(
            "AuditPoolStateObserver", consumer.get_pool, "AuditorWorker"
        )

    def grep(self, consumer, *args):
        """
        Log the thread state for grep plugins

        :param consumer: A grep consumer instance
        :param args: Fuzzable requests that we don't care about
        :return: None, everything is written to disk
        """
        self._observe_pool_once(
            "GrepPoolStateObserver", consumer.get_pool, "GrepWorker"
        )

    def _observe_pool_once(self, thread_name, get_pool, worker_name):
        """
        Start a thread which logs the state of the pool, unless it was already
        started by a previous call.
        """
        with self._threads_lock:
            if thread_name in self._threads:
                return

            thread = threading.Thread(
                target=self.thread_worker,
                args=(get_pool(), worker_name),
                name=thread_name,
            )
            self._threads[thread_name] = thread
            thread.start()

    def thread_worker(self, pool, name):
        """
        Log the pool state every ANALYZE_EVERY seconds until end() is called,
        which makes the thread finish in at most POLL_INTERVAL seconds.
        """
        last_call = 0.0

        while not self._stop.is_set():
            current_time = time.time()

            if (current_time - last_call) >= self.ANALYZE_EVERY:
                last_call = current_time
                self.log_pool_state(pool, name)

            self._stop.wait(self.POLL_INTERVAL)

    def log_pool_state(self, pool, name):
        inspect_data = self.add_thread_stack(pool.inspect_threads())
        self.inspect_data_to_log(pool, inspect_data)

        internal_thread_data = pool.get_internal_thread_state()
        self.internal_thread_data_to_log(name, internal_thread_data)

        pool_queue_sizes = pool.get_pool_queue_sizes()
        self.pool_queue_sizes_to_log(name, pool_queue_sizes)

    def add_thread_stack(self, inspect_data):
        """
        When threads have been running for a long time, it is not enough to
        log the initial function that the worker was told to run, we want to
        know exactly what function the thread is running *now*, including the
        whole traceback.
        """
        workers_to_inspect = {
            worker_state["worker_id"]
            for worker_state in inspect_data
            if self._has_been_running_for(worker_state, self.STACK_TRACE_MIN_TIME)
        }

        #
        #   If there is nothing to do, just return to reduce the performance
        #   impact of this function
        #
        if not workers_to_inspect:
            return inspect_data

        threads_by_id = {thread.ident: thread for thread in threading.enumerate()}

        for thread_id, frame in list(sys._current_frames().items()):
            thread = threads_by_id.get(thread_id)

            if thread is None or not hasattr(thread, "get_state"):
                continue

            worker_id = thread.get_state()["worker_id"]

            if worker_id not in workers_to_inspect:
                continue

            trace_lines = [
                f"{filename}:{lineno} @ {name}()"
                for filename, lineno, name, _ in traceback.extract_stack(frame)
            ]
            trace = ", ".join(trace_lines[-10:])

            for worker_state in inspect_data:
                if worker_state["worker_id"] == worker_id:
                    worker_state["trace"] = trace

        return inspect_data

    @staticmethod
    def _running_time(worker_state):
        """
        :return: The seconds the worker has been running its current job, None
                 for idle workers.
        """
        if worker_state["idle"] or worker_state["start_time"] is None:
            return None

        return time.time() - worker_state["start_time"]

    def _has_been_running_for(self, worker_state, min_time):
        running_time = self._running_time(worker_state)
        return running_time is not None and running_time >= min_time

    def pool_queue_sizes_to_log(self, name, pool_queue_sizes):
        inqueue_size = pool_queue_sizes.get("inqueue_size", None)
        outqueue_size = pool_queue_sizes.get("outqueue_size", None)

        msg = "%s worker pool has %s tasks in inqueue and %s tasks in outqueue"
        args = (name, inqueue_size, outqueue_size)

        self.write_to_log(msg % args)

    def internal_thread_data_to_log(self, name, internal_thread_data):
        worker_handler = internal_thread_data["worker_handler"]
        task_handler = internal_thread_data["task_handler"]
        result_handler = internal_thread_data["result_handler"]

        msg = (
            "%s worker pool internal thread state:"
            " (worker: %s, task: %s, result: %s)"
        )
        args = (name, worker_handler, task_handler, result_handler)

        self.write_to_log(msg % args)

    def inspect_data_to_log(self, pool, inspect_data):
        """
        Print the inspect_threads data to the log files

        def get_state(self):
            return {'func_name': self.func_name,
                    'args': self.args,
                    'kwargs': self.kwargs,
                    'start_time': self.start_time,
                    'idle': self.is_idle(),
                    'job': self.job,
                    'worker_id': self.id}

        :return: None
        """
        name = pool.worker_names

        if not len(inspect_data):
            self.write_to_log(f"No pool workers at {name}.")
            return

        idle_workers = [
            worker_state for worker_state in inspect_data if worker_state["idle"]
        ]

        #
        #   Write the detailed information. Save us some disk space and
        #   sanity, only log worker state if it has been running for a while
        #
        for worker_state in inspect_data:
            if self._has_been_running_for(worker_state, self.MIN_RUNNING_TIME_TO_LOG):
                self.write_to_log(self._running_worker_message(worker_state))

        #
        #   Write the idle workers all together at the end, this makes
        #   the log easier to read
        #
        for worker_state in idle_workers:
            message = "Worker with ID %s(%s) is idle."
            message %= (worker_state["name"], worker_state["worker_id"])
            self.write_to_log(message)

        idle_perc = len(idle_workers) / len(inspect_data) * 100
        self.write_to_log(f"{int(idle_perc)}% of {name} workers are idle.")

    def _running_worker_message(self, worker_state):
        args_str = ", ".join(self._short_repr(arg) for arg in worker_state["args"])

        short_kwargs = {
            key: self._short_repr(value)
            for key, value in worker_state["kwargs"].items()
        }
        kwargs_str = smart_unicode(short_kwargs)

        func_name = smart_unicode(worker_state["func_name"])
        func_name = self.clean_function_name(func_name)

        message = (
            "Worker with ID %s(%s) has been running job %s for %.2f seconds."
            " The job is: %s(%s, kwargs=%s)"
        )
        message %= (
            worker_state["name"],
            worker_state["worker_id"],
            worker_state["job"],
            self._running_time(worker_state),
            func_name,
            args_str,
            kwargs_str,
        )

        trace = worker_state.get("trace", None)
        if trace is not None:
            message += f". Function call tree: {trace}"

        return message

    def _short_repr(self, value):
        value_str = smart_unicode(repr(value))

        if len(value_str) > self.MAX_ARGUMENT_LENGTH:
            value_str = value_str[: self.MAX_ARGUMENT_LENGTH] + "...'"

        return value_str

    def write_to_log(self, message):
        self._output.debug(message)

    def clean_function_name(self, function_name):
        if self.DISCOVER_WORKER_RE.search(function_name):
            return "_discover_worker"

        return function_name
