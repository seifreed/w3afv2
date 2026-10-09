"""
test_history.py

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

from w3af.core.ui.console.history import history, historyTable


class TestHistoryTable(unittest.TestCase):
    def test_creates_and_reuses_history_per_key(self):
        table = historyTable()
        first = table.get_history("menu")
        second = table.get_history("menu")
        self.assertIs(first, second)
        self.assertIsInstance(first, history)

    def test_distinct_keys_get_distinct_history(self):
        table = historyTable()
        self.assertIsNot(table.get_history("a"), table.get_history("b"))


class TestHistory(unittest.TestCase):
    def test_back_on_empty_returns_none(self):
        self.assertIsNone(history().back())

    def test_remember_and_navigate_back(self):
        h = history()
        h.remember(["first"])
        h.remember(["second"])

        self.assertEqual(h.back(["pending"]), ["second"])
        self.assertEqual(h.back(), ["first"])
        # Already at the oldest entry: no further history
        self.assertIsNone(h.back())

    def test_forward_restores_pending_line(self):
        h = history()
        h.remember(["only"])

        self.assertEqual(h.back(["draft"]), ["only"])
        # Moving forward past the end restores the pending line being typed
        self.assertEqual(h.forward(), ["draft"])

    def test_forward_without_back_returns_none(self):
        h = history()
        h.remember(["cmd"])
        self.assertIsNone(h.forward())

    def test_forward_between_entries(self):
        h = history()
        h.remember(["a"])
        h.remember(["b"])
        h.remember(["c"])

        h.back()
        h.back()
        self.assertEqual(h.forward(), ["c"])

    def test_forward_past_end_without_pending_returns_none(self):
        h = history()
        h.remember(["a"])
        h.back()  # pending is None
        self.assertIsNone(h.forward())
