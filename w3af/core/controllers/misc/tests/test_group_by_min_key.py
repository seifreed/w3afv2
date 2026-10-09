"""
test_group_by_min_key.py

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

from w3af.core.controllers.misc.group_by_min_key import group_by_min_key


class TestGroupByMinKey(unittest.TestCase):
    def test_group_by_first_item(self):
        self.assertEqual(
            group_by_min_key([("a", 1), ("a", 2), ("a", 3)]), ({"a": [1, 2, 3]}, 0)
        )

    def test_group_by_second_item(self):
        self.assertEqual(
            group_by_min_key([(1, "a"), (2, "a"), (3, "a")]), ({"a": [1, 2, 3]}, 1)
        )

    def test_group_by_second_item_with_many_keys(self):
        self.assertEqual(
            group_by_min_key([(1, "a"), (2, "a"), (3, "a"), (56, "d")]),
            ({"a": [1, 2, 3], "d": [56]}, 1),
        )

    def test_tie_prefers_first_item(self):
        self.assertEqual(
            group_by_min_key([("a", 1), ("b", 2)]), ({"a": [1], "b": [2]}, 0)
        )
