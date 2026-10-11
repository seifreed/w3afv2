"""
test_seed.py

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
import unittest

import w3af.core.controllers.output_manager as om
from w3af.core.constants import POISON_PILL
from w3af.core.controllers.core_helpers.consumers.seed import seed
from w3af.core.controllers.core_helpers.consumers.tests.consumer_plugins import (
    drain_results,
)
from w3af.core.controllers.tests.local_http_server import LocalHTTPServer, Reply
from w3af.core.controllers.tests.recording_output import start_recording_output
from w3af.core.controllers.w3af_core import w3afCore
from w3af.core.data.kb.knowledge_base import DBKnowledgeBase
from w3af.core.data.parsers.doc.url import URL
from w3af.core.exceptions import ScanMustStopException


class TestSeedConsumer(unittest.TestCase):
    def setUp(self):
        self.server = LocalHTTPServer(lambda method, path: Reply(body="seed"))
        self.server.start()
        self.addCleanup(self.server.close)
        self.core = w3afCore(knowledge_base=kb)
        self.addCleanup(self.core.worker_pool.terminate_join)
        self.addCleanup(kb.cleanup)
        self.recorder = start_recording_output()
        self.consumer = seed(self.core, kb, om.out)

    def errors(self):
        return self.recorder.messages_of("error")

    def test_seeds_reachable_targets(self):
        target = URL(self.server.url("/"))

        self.consumer.seed_output_queue([target])

        self.assertTrue(self.consumer.has_pending_work())
        plugin_name, request, fuzzable_request = self.consumer.get_result()
        self.assertEqual((plugin_name, request), (None, None))
        self.assertEqual(fuzzable_request.get_uri(), target)
        self.assertEqual(self.consumer.get_result(), POISON_PILL)
        self.assertFalse(self.consumer.has_pending_work())
        self.assertEqual(list(kb.get_all_known_fuzzable_requests()), [fuzzable_request])

    def test_unsupported_protocol_is_reported(self):
        self.consumer.seed_output_queue([URL("ftp://127.0.0.1/")])

        self.assertEqual(drain_results(self.consumer), [POISON_PILL])
        self.assertEqual(
            self.errors(),
            [
                (
                    'The target URL: "ftp://127.0.0.1/" is unreachable. Exception:'
                    ' "Unsupported URL: "ftp://127.0.0.1/"".'
                )
            ],
        )

    def test_unexpected_error_is_reported(self):
        self.consumer.seed_output_queue([self.server.url("/")])

        self.assertEqual(drain_results(self.consumer), [POISON_PILL])
        (error,) = self.errors()
        self.assertIn("is unreachable because of an unhandled exception", error)
        self.assertIn("Traceback for this error", error)

    def test_stopped_scan_is_raised(self):
        self.core.uri_opener.stop()

        with self.assertRaises(ScanMustStopException):
            self.consumer.seed_output_queue([URL(self.server.url("/"))])

        self.assertEqual(self.errors(), ["The target server is unreachable. Stopping."])

    def test_terminate_clears_output_queue(self):
        self.consumer.seed_output_queue([URL(self.server.url("/"))])

        self.consumer.terminate()

        self.assertIsNone(self.consumer.join())
        self.assertRaises(queue.Empty, self.consumer.get_result)
        self.assertIs(self.consumer.out_queue, self.consumer._out_queue)
        self.assertEqual(self.consumer.get_name(), "Seed")


kb = DBKnowledgeBase()
