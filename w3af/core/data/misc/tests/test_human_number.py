"""
test_human_number.py

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

from w3af.core.data.misc.human_number import human_number


class TestHumanNumber(unittest.TestCase):
    def test_converts_numbers_from_one_to_ten(self):
        expected = (
            "one",
            "two",
            "three",
            "four",
            "five",
            "six",
            "seven",
            "eight",
            "nine",
            "ten",
        )

        for number, word in enumerate(expected, start=1):
            with self.subTest(number=number):
                self.assertEqual(human_number(number), word)

    def test_rejects_numbers_outside_supported_range(self):
        for number in (0, 11):
            with self.subTest(number=number), self.assertRaises(KeyError):
                human_number(number)
