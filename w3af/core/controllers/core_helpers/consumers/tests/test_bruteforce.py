"""
test_bruteforce.py

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
import unittest

import w3af.core.controllers.output_manager as om
from w3af.core.constants import POISON_PILL
from w3af.core.controllers.core_helpers.consumers.bruteforce import bruteforce
from w3af.core.controllers.core_helpers.consumers.tests.consumer_plugins import (
    CrashingObserver,
    crashing_bruteforce,
    drain_results,
    prepare_plugins,
    recording_bruteforce,
    reported_errors,
    stopping_bruteforce,
)
from w3af.core.controllers.tests.recording_output import start_recording_output
from w3af.core.controllers.w3af_core import w3afCore
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.request.fuzzable_request import FuzzableRequest

LOGIN_FORM = FuzzableRequest(URL("http://127.0.0.1/login"))
AUTHENTICATED = FuzzableRequest(URL("http://127.0.0.1/admin"))


class TestBruteforceConsumer(unittest.TestCase):
    def setUp(self):
        self.core = w3afCore()
        self.addCleanup(self.core.worker_pool.terminate_join)
        self.recorder = start_recording_output()

    def run_bruteforce(self, plugins, observer=None):
        consumer = bruteforce(prepare_plugins(plugins, self.core), self.core, om.out)
        if observer is not None:
            consumer.add_observer(observer)
        consumer.start()

        consumer.in_queue_put(LOGIN_FORM)
        consumer.join()
        return consumer

    def assert_end_logged(self, suffix):
        expected = re.compile(
            r"Spent \d+\.\d\d seconds running \w+\.end\(\)" + re.escape(suffix) + "$"
        )
        debug_messages = self.recorder.messages_of("debug")
        self.assertTrue(
            any(expected.match(message) for message in debug_messages),
            debug_messages,
        )

    def test_found_requests_are_sent_to_the_output_queue(self):
        plugin = recording_bruteforce(found=[AUTHENTICATED])

        consumer = self.run_bruteforce([plugin])

        self.assertEqual(plugin.bruteforced, [LOGIN_FORM])
        self.assertEqual(
            drain_results(consumer),
            [("recording_bruteforce", LOGIN_FORM, AUTHENTICATED), POISON_PILL],
        )
        self.assert_end_logged("")

    def test_plugin_errors_are_reported(self):
        consumer = self.run_bruteforce([crashing_bruteforce()])

        self.assertEqual(
            reported_errors(consumer),
            [
                ("crashing_bruteforce", "bruteforce failed"),
                ("crashing_bruteforce", "bruteforce end failed"),
            ],
        )
        self.assert_end_logged(" until an unhandled exception was found")

    def test_scan_must_stop_in_end(self):
        consumer = self.run_bruteforce([stopping_bruteforce()])

        self.assertEqual(reported_errors(consumer), [])
        self.assert_end_logged(" until a scan must stop exception was raised")

    def test_observer_errors_are_reported(self):
        plugin = recording_bruteforce()

        consumer = self.run_bruteforce([plugin], observer=CrashingObserver())

        self.assertEqual(plugin.bruteforced, [LOGIN_FORM])
        self.assertEqual(
            reported_errors(consumer),
            [("bruteforce._run_observers()", "bruteforce observer failed")],
        )
