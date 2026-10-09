"""
helper.py

Copyright 2012 Andres Riancho

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
import re
import sys
import unittest

import w3af.core.data.kb.knowledge_base as kb

ANSI_ESCAPE = re.compile(r"\x1b[^m]*m")


class CapturedStdout:
    def __init__(self):
        self.messages = []

    def write(self, msg):
        msg = ANSI_ESCAPE.sub("", msg)
        self.messages.extend(msg.split("\n\r"))

    def flush(self):
        pass

    def clear(self):
        self.messages = []


class ConsoleTestHelper(unittest.TestCase):
    """
    Helper class to build console UI tests.
    """

    console = None
    OUTPUT_FILE = "output-w3af-unittest.txt"
    OUTPUT_HTTP_FILE = "output-w3af-unittest-http.txt"

    def setUp(self):
        kb.kb.cleanup()
        self.capture_sys()

    def tearDown(self):
        self.restore_sys()
        self._mock_stdout.clear()

        #
        # I want to make sure that we don't have *any hidden* exceptions
        # in our tests.
        #
        if self.console is not None:
            caught_exceptions = (
                self.console._w3af.exception_handler.get_all_exceptions()
            )
            msg = [e.get_summary() for e in caught_exceptions]
            self.assertEqual(len(caught_exceptions), 0, msg)

        # Remove all temp files
        for fname in (self.OUTPUT_FILE, self.OUTPUT_HTTP_FILE):
            if os.path.exists(fname):
                os.remove(fname)

    def capture_sys(self):
        # backup
        self.old_stdout = sys.stdout
        self.old_exit = sys.exit
        self.exit_calls = []

        # assign new
        self._mock_stdout = CapturedStdout()
        sys.stdout = self._mock_stdout
        sys.exit = self._record_exit

    def _record_exit(self, status=0):
        self.exit_calls.append(status)

    def restore_sys(self):
        sys.stdout = self.old_stdout
        sys.exit = self.old_exit

    def clear_stdout_messages(self):
        self._mock_stdout.clear()

    def startswith_expected_in_output(self, expected):
        for line in expected:
            for sys_line in self._mock_stdout.messages:
                if sys_line.startswith(line):
                    break
            else:
                return False, self.generate_msg(line)
        return True, "OK"

    def all_expected_in_output(self, expected):
        for line in expected:
            if line not in self._mock_stdout.messages:
                return False, self.generate_msg(line)
        return True, "OK"

    def all_expected_substring_in_output(self, expected):
        for e_substring in expected:

            for output_line in self._mock_stdout.messages:
                if e_substring in output_line:
                    break

            else:
                return False, self.generate_msg(e_substring)
        return True, "OK"

    def error_in_output(self, errors):
        for line in self._mock_stdout.messages:
            for error_str in errors:
                if error_str in line:
                    return True

        return False

    def generate_msg(self, line):
        msg = '"%s" was not found in:\n%s'
        return msg % (line, "".join(self._mock_stdout.messages))
