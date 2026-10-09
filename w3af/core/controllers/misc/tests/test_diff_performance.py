"""
test_diff_performance.py

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

import os
import time
import unittest
from pathlib import Path

from w3af import ROOT_PATH
from w3af.core.controllers.misc.diff import chunked_diff

LINES = 10000
MAX_SECONDS = 30


def growing_lines(changed_line=None):
    return "".join(("B" if i == changed_line else "A") * i + "\n" for i in range(LINES))


class TestDiffPerformance(unittest.TestCase):

    DATA = os.path.join(ROOT_PATH, "core", "controllers", "misc", "tests", "data")

    def assert_fast_diff(self, a, b):
        start = time.monotonic()
        result = chunked_diff(a, b)
        self.assertLess(time.monotonic() - start, MAX_SECONDS)
        return result

    def test_xml(self):
        a = Path(self.DATA, "source.xml").read_text()
        b = Path(self.DATA, "target.xml").read_text()

        a_unique, b_unique = self.assert_fast_diff(a, b)

        self.assertLess(len(a_unique), len(a))
        self.assertLess(len(b_unique), len(b))

    def test_diff_large_different_responses(self):
        changed = LINES - 3

        result = self.assert_fast_diff(growing_lines(), growing_lines(changed))

        self.assertEqual(result, ("A" * changed, "B" * changed))

    def test_large_equal_responses(self):
        large_file = growing_lines()

        self.assertEqual(self.assert_fast_diff(large_file, large_file), ("", ""))
