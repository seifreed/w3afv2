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

import unittest

from w3af.core.controllers.core_helpers.consumers.base_consumer import BaseConsumer
from w3af.core.controllers.w3af_core import w3afCore
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.request.fuzzable_request import FuzzableRequest


class TeardownCountingConsumer(BaseConsumer):
    """
    A consumer with no plugins whose teardown only counts how many times the
    consumer loop asked for it.
    """

    def __init__(self, w3af_core):
        super().__init__([], w3af_core, "TestConsumer")
        self.teardown_calls = 0

    def _teardown(self):
        self.teardown_calls += 1


class TestBaseConsumer(unittest.TestCase):

    def setUp(self):
        self.core = w3afCore()
        self.bc = TeardownCountingConsumer(self.core)

    def tearDown(self):
        self.core.worker_pool.terminate_join()

    def test_handle_exception(self):
        url = URL("http://moth/")
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

    def test_terminate(self):
        self.bc.start()
        self.bc.terminate()

        self.assertEqual(self.bc.teardown_calls, 1)

    def test_terminate_terminate(self):
        self.bc.start()
        self.bc.terminate()
        self.bc.terminate()

        self.assertEqual(self.bc.teardown_calls, 1)
