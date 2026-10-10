"""
test_auth.py

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

import unittest

import w3af.core.controllers.output_manager as om
from w3af.core.controllers.core_helpers.consumers.auth import auth
from w3af.core.controllers.core_helpers.consumers.tests.consumer_plugins import (
    WAIT_TIMEOUT,
    counting_auth,
    crashing_auth,
    drain_results,
    reported_errors,
)
from w3af.core.controllers.w3af_core import w3afCore

NEVER = 60


class TestAuthConsumer(unittest.TestCase):
    def setUp(self):
        self.core = w3afCore()
        self.addCleanup(self.core.worker_pool.terminate_join)

    def start_consumer(self, plugins, timeout):
        consumer = auth(plugins, self.core, timeout, om.out)
        consumer.start()
        return consumer

    def test_name(self):
        consumer = auth([], self.core, NEVER, om.out)
        self.assertEqual(consumer.get_name(), "Authenticator")

    def test_login_after_timeout(self):
        plugin = counting_auth()
        consumer = self.start_consumer([plugin], timeout=0.01)

        self.assertTrue(plugin.login_event.wait(WAIT_TIMEOUT))
        consumer.join()

        self.assertGreaterEqual(plugin.logins, 1)
        self.assertEqual(plugin.end_calls, 1)
        self.assertTrue(consumer.has_finished())
        self.assertEqual(drain_results(consumer), [])

    def test_async_force_login(self):
        plugin = counting_auth()
        consumer = self.start_consumer([plugin], timeout=NEVER)

        consumer.async_force_login()

        self.assertTrue(plugin.login_event.wait(WAIT_TIMEOUT))
        consumer.join()
        self.assertEqual(plugin.logins, 1)

    def test_force_login_with_active_session(self):
        plugin = counting_auth(active_session=True)
        consumer = auth([plugin], self.core, NEVER, om.out)

        consumer.force_login()

        self.assertEqual(plugin.logins, 0)
        self.assertFalse(consumer.has_pending_work())

    def test_login_errors_are_reported(self):
        consumer = auth([crashing_auth()], self.core, NEVER, om.out)

        consumer.force_login()

        self.assertEqual(
            reported_errors(consumer), [("crashing_auth", "session check failed")]
        )
