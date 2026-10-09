"""
test_safe_deepcopy.py

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

from w3af.core.controllers.misc.safe_deepcopy import safe_deepcopy


class ChangesDuringFirstCopy:
    """
    Fails the first deep copy like a dict which changed size during iteration
    """

    def __init__(self):
        self.copies = 0
        self.items = {"a": [1]}

    def __deepcopy__(self, memo):
        self.copies += 1
        if self.copies == 1:
            raise RuntimeError("dictionary changed size during iteration")

        clone = ChangesDuringFirstCopy()
        clone.items = {key: list(value) for key, value in self.items.items()}
        return clone


class TestSafeDeepcopy(unittest.TestCase):
    def test_copy_is_independent(self):
        original = {"a": [1, 2]}

        copied = safe_deepcopy(original)
        copied["a"].append(3)

        self.assertEqual(original, {"a": [1, 2]})

    def test_retries_after_a_race_condition(self):
        original = ChangesDuringFirstCopy()

        copied = safe_deepcopy(original)

        self.assertEqual(original.copies, 2)
        self.assertEqual(copied.items, {"a": [1]})
        self.assertIsNot(copied.items, original.items)
