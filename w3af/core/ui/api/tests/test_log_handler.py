"""
test_log_handler.py

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

import os
import threading
import unittest

from w3af.core.data.constants.severity import HIGH
from w3af.core.ui.api.utils.log_handler import RESTAPIOutput


class RESTAPIOutputTest(unittest.TestCase):
    def setUp(self):
        self.output = RESTAPIOutput()
        self.addCleanup(self.output.cleanup)

    def test_stores_messages_of_every_type(self):
        self.output.debug("debug message")
        self.output.information("information message")
        self.output.error("error message")
        self.output.vulnerability("vulnerability message", severity=HIGH)
        self.output.console("console message")

        entries = [entry.to_json() for entry in self.output.get_entries(0, 10)]

        self.assertEqual(len(self.output), 5)
        self.assertEqual(
            [(entry["id"], entry["type"]) for entry in entries],
            [
                (0, "debug"),
                (1, "information"),
                (2, "error"),
                (3, "vulnerability"),
                (4, "console"),
            ],
        )
        self.assertEqual(entries[3]["severity"], HIGH)
        self.assertEqual(entries[3]["message"], "vulnerability message")
        self.assertIsNone(entries[0]["severity"])

    def test_messages_written_from_another_thread_are_readable(self):
        writer = threading.Thread(target=self.output.information, args=("hello",))
        writer.start()
        writer.join()

        entries = list(self.output.get_entries(0, 1))
        self.assertEqual(entries[0].get_msg(), "hello")

    def test_cleanup_removes_the_log_files(self):
        self.output.information("hello")
        backend = self.output.get_db_backend()

        self.output.cleanup()

        for suffix in (".dat", ".dir", ".bak"):
            self.assertFalse(os.path.exists(backend + suffix))
