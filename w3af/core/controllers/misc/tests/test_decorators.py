"""
test_decorators.py

Copyright 2026 w3af contributors

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

from w3af.core.controllers.misc.decorators import retry, runonce
from w3af.core.controllers.tests.recording_output import recording_output


class AlreadyRan(Exception):
    pass


class Plugin:
    def __init__(self):
        self.calls = 0

    @runonce(exc_class=AlreadyRan)
    def discover(self, value):
        self.calls += 1
        return value


class Flaky:
    def __init__(self, failures):
        self.failures = failures
        self.calls = 0

    def __call__(self):
        self.calls += 1
        if self.calls <= self.failures:
            raise ValueError(f"failure {self.calls}")
        return "ok"


class TestRunOnce(unittest.TestCase):
    def test_second_call_raises(self):
        plugin = Plugin()

        self.assertEqual(plugin.discover(1), 1)
        self.assertRaises(AlreadyRan, plugin.discover, 2)
        self.assertEqual(plugin.calls, 1)

    def test_each_instance_runs_once(self):
        self.assertEqual(Plugin().discover("a"), "a")
        self.assertEqual(Plugin().discover("b"), "b")


class TestRetry(unittest.TestCase):
    def test_invalid_backoff(self):
        self.assertRaises(ValueError, retry, 2, backoff=1)

    def test_invalid_tries(self):
        self.assertRaises(ValueError, retry, 0.5)

    def test_invalid_delay(self):
        self.assertRaises(ValueError, retry, 2, delay=-1)

    def test_succeeds_after_failures(self):
        flaky = Flaky(failures=2)
        output = recording_output()

        result = retry(3, delay=0, log_msg="retrying", output=output)(flaky)()

        self.assertEqual(result, "ok")
        self.assertEqual(flaky.calls, 3)
        self.assertEqual(
            output.messages, [("debug", "retrying"), ("debug", "retrying")]
        )

    def test_log_message_requires_output(self):
        with self.assertRaisesRegex(ValueError, "'output' is required"):
            retry(2, delay=0, log_msg="retrying")

    def test_reraises_last_exception(self):
        flaky = Flaky(failures=5)

        with self.assertRaisesRegex(ValueError, "failure 2"):
            retry(2, delay=0)(flaky)()

    def test_raises_exc_class_with_original_message(self):
        flaky = Flaky(failures=5)

        with self.assertRaisesRegex(RuntimeError, "failure 1"):
            retry(1, delay=0, exc_class=RuntimeError)(flaky)()

    def test_raises_exc_class_with_custom_message(self):
        flaky = Flaky(failures=5)

        with self.assertRaisesRegex(RuntimeError, "gave up"):
            retry(1, delay=0, exc_class=RuntimeError, err_msg="gave up")(flaky)()
