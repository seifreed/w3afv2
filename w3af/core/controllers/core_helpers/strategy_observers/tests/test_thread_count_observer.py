"""
test_thread_count_observer.py

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
from w3af.core.controllers.core_helpers.strategy_observers.strategy_observer import (
    StrategyObserver,
)
from w3af.core.controllers.core_helpers.strategy_observers.thread_count_observer import (
    ThreadCountObserver,
)
from w3af.core.controllers.tests.recording_output import start_recording_output


class TestThreadCountObserver(unittest.TestCase):
    def setUp(self):
        self.recorder = start_recording_output()
        self.addCleanup(om.manager.get_output_plugin_inst().remove, self.recorder)

    def thread_count_messages(self):
        return [
            message
            for message in self.recorder.messages_of("debug")
            if message.startswith("The framework has ")
        ]

    def test_logs_the_active_threads_once_every_period(self):
        observer = ThreadCountObserver(om.out)

        observer.crawl(None, None)
        observer.audit(None, None)
        observer.bruteforce(None, None)
        observer.grep(None, None, None)

        messages = self.thread_count_messages()
        self.assertEqual(len(messages), 1, messages)
        self.assertRegex(messages[0], r"^The framework has \d+ active threads\.$")


class TestStrategyObserver(unittest.TestCase):
    def test_hooks_ignore_the_events(self):
        observer = StrategyObserver()

        self.assertIsNone(observer.crawl(None, None))
        self.assertIsNone(observer.audit(None, None))
        self.assertIsNone(observer.bruteforce(None, None))
        self.assertIsNone(observer.grep(None, None, None))
        self.assertIsNone(observer.end())
