"""
test_grep.py

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

import w3af.core.data.kb.config as cf
import w3af.core.data.kb.knowledge_base as kb
from w3af.core.controllers.core_helpers.consumers.grep import grep
from w3af.core.controllers.core_helpers.consumers.tests.consumer_plugins import (
    CrashingObserver,
    crashing_grep,
    recording_grep,
    reported_errors,
)
from w3af.core.controllers.tests.local_http_server import LocalHTTPServer, Reply
from w3af.core.controllers.tests.recording_output import start_recording_output
from w3af.core.controllers.w3af_core import w3afCore
from w3af.core.data.parsers.doc.url import URL


def body_per_path(method, path):
    if path.startswith("/same-body"):
        return Reply(body="same body")
    return Reply(body=f"body for {path}")


class GrepConsumerTest(unittest.TestCase):
    def setUp(self):
        self.server = LocalHTTPServer(body_per_path).start()
        self.addCleanup(self.server.close)
        self.core = w3afCore()
        self.addCleanup(self.core.worker_pool.terminate_join)
        self.addCleanup(kb.kb.cleanup)
        cf.cf.save("target_domains", {"127.0.0.1"})
        self.addCleanup(cf.cf.save, "target_domains", set())
        self.recorder = start_recording_output()

    def start_consumer(self, plugins, observer=None):
        consumer = grep(plugins, self.core)
        if observer is not None:
            consumer.add_observer(observer)
        self.core.uri_opener.set_grep_queue_put(consumer.grep)
        self.addCleanup(self.core.uri_opener.set_grep_queue_put, None)
        consumer.start()
        return consumer

    def get(self, path, host="127.0.0.1"):
        url = f"http://{host}:{self.server.port}{path}"
        return self.core.uri_opener.GET(URL(url), cache=True)


class TestGrepConsumer(GrepConsumerTest):
    def test_grep_plugins_analyze_new_responses(self):
        plugin = recording_grep()
        consumer = self.start_consumer([plugin])

        for path in ("/a", "/a", "/same-body-1", "/same-body-2"):
            self.get(path)
        self.get("/out-of-scope", host="localhost")

        consumer.join()

        expected = sorted([self.server.url("/a"), self.server.url("/same-body-1")])
        self.assertEqual(sorted(plugin.grepped), expected)
        self.assertEqual(
            consumer._should_grep_stats,
            {
                "accept": 2,
                "reject-seen-body": 1,
                "reject-seen-url": 1,
                "reject-out-of-scope": 1,
            },
        )
        self.assertEqual(plugin.end_calls, 1)
        self.assertEqual(reported_errors(consumer), [])

    def test_nothing_is_grepped_after_teardown(self):
        consumer = self.start_consumer([recording_grep()])
        consumer.join()

        response = self.get("/after-teardown")

        self.assertFalse(consumer.should_grep(None, response))

    def test_plugin_errors_are_reported(self):
        plugin = recording_grep()
        consumer = self.start_consumer(
            [crashing_grep(), plugin], observer=CrashingObserver()
        )

        self.get("/error")
        consumer.join()

        self.assertEqual(plugin.grepped, [self.server.url("/error")])
        self.assertEqual(
            sorted(reported_errors(consumer)),
            [
                ("crashing_grep", "grep failed"),
                ("grep._run_observers()", "grep observer failed"),
            ],
        )
        (end_error,) = self.core.exception_handler.get_all_exceptions()
        self.assertEqual(end_error.plugin, "crashing_grep")
        self.assertEqual(end_error.phase, "grep")
        self.assertIn(
            'An exception was found while running crashing_grep.end(): "grep end'
            ' failed"',
            self.recorder.messages_of("debug"),
        )

    def test_queue_sizes_are_logged_every_25_calls(self):
        consumer = grep([recording_grep()], self.core)
        self.addCleanup(consumer._shutdown_threadpool)
        consumer.send_poison_pill()

        def logged_queue_sizes():
            prefix = "The Grep input queue received the POISON_PILL"
            debug_messages = self.recorder.messages_of("debug")
            return len([m for m in debug_messages if m.startswith(prefix)])

        for _ in range(grep.LOG_QUEUE_SIZES_EVERY - 1):
            consumer._log_queue_sizes()
        self.assertEqual(logged_queue_sizes(), 0)

        consumer._log_queue_sizes()
        self.assertEqual(logged_queue_sizes(), 1)


class TestRequestResponseLoading(GrepConsumerTest):
    def setUp(self):
        super().setUp()
        self.plugin = recording_grep()
        self.consumer = grep([self.plugin], self.core)
        self.addCleanup(self.consumer._shutdown_threadpool)
        self.response = self.get("/stored")

    def test_loaded_responses_are_cached(self):
        request, response = self.consumer._get_request_response_from_id(
            self.response.id
        )

        self.assertEqual(request.get_uri(), self.response.get_uri())
        self.assertEqual(response.get_body(), "body for /stored")
        self.assertEqual(
            self.consumer._get_request_response_from_id(self.response.id),
            (request, response),
        )

    def test_waits_for_the_thread_which_loads_the_response(self):
        event = threading.Event()
        self.consumer._request_response_processes[self.response.id] = event
        loaded = []

        reader = threading.Thread(
            target=lambda: loaded.append(
                self.consumer._get_request_response_from_id(self.response.id)
            )
        )
        reader.start()

        self.consumer._request_response_lru[self.response.id] = ("req", "resp")
        event.set()
        reader.join()

        self.assertEqual(loaded, [("req", "resp")])

    def test_loads_the_response_when_the_other_thread_result_is_gone(self):
        event = threading.Event()
        event.set()
        self.consumer._request_response_processes[self.response.id] = event

        _, response = self.consumer._get_request_response_from_id(self.response.id)

        self.assertEqual(response.get_body(), "body for /stored")

    def test_timeout_waiting_for_the_other_thread(self):
        self.consumer.DESERIALIZATION_TIMEOUT = 0.01
        self.consumer._request_response_processes[self.response.id] = threading.Event()

        self.consumer._run_one_plugin("recording_grep", self.response.id)

        self.assertEqual(self.plugin.grepped, [])
        self.assertEqual(
            self.recorder.messages_of("error"),
            [
                (
                    "There was a timeout waiting for the deserialization of HTTP"
                    f" request and response with id {self.response.id}"
                )
            ],
        )

    def test_unknown_plugin(self):
        self.consumer._run_one_plugin("unknown", self.response.id)

        self.assertEqual(self.plugin.grepped, [])
        self.assertEqual(
            self.recorder.messages_of("error"),
            [
                (
                    "Internal error in grep consumer: plugin with name unknown does"
                    " not exist in dict."
                )
            ],
        )
