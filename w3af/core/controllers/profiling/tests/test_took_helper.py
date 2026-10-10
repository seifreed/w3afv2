"""
test_took_helper.py

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

import queue
import time
import unittest

from w3af.core.controllers.output_manager.log_sink import LogSink
from w3af.core.controllers.profiling.took_helper import TookLine
from w3af.core.controllers.w3af_core import w3afCore


class TestTookHelper(unittest.TestCase):
    def send_took_line(self, w3af_core):
        messages = queue.Queue()

        took_line = TookLine(
            w3af_core,
            "plugin_name",
            "method_name",
            debugging_id="ML7aEYsa",
            method_params={"test": "yes"},
            log_sink=LogSink(messages),
        )
        took_line.send()

        (method, sent_message), _kwargs = messages.get(timeout=1)
        self.assertEqual(method, "debug")
        self.assertTrue(messages.empty())
        return sent_message

    def test_took_simple(self):
        sent_message = self.send_took_line(w3afCore())

        self.assertRegex(
            sent_message,
            r'^plugin_name.method_name\(test="yes",did="ML7aEYsa"\)'
            r" took \d+\.\d{2}s to run$",
        )

    def test_took_with_rtt(self):
        w3af_core = w3afCore()
        w3af_core.uri_opener._rtt_sum_debugging_id["ML7aEYsa"] = 1.8

        sent_message = self.send_took_line(w3af_core)

        self.assertRegex(
            sent_message,
            r'^plugin_name.method_name\(test="yes",did="ML7aEYsa"\)'
            r" took \d+\.\d{2}s to run \(1.80s \d+% sending HTTP requests\)$",
        )

    def test_took_with_cpu_bound_work(self):
        w3af_core = w3afCore()
        messages = queue.Queue()
        took_line = TookLine(
            w3af_core,
            "plugin_name",
            "method_name",
            log_sink=LogSink(messages),
        )

        busy_until = time.thread_time() + 0.3
        while time.thread_time() < busy_until:
            pass

        took_line.send()

        (_method, sent_message), _kwargs = messages.get(timeout=1)
        self.assertRegex(
            sent_message,
            r"^plugin_name.method_name\(\) took \d+\.\d{2}s to run"
            r" \(\d+\.\d{2}s \d+% consuming CPU cycles\)$",
        )
