"""
test_util.py

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

from w3af.core.ui.console.util import commonPrefix, mapDict, splitPath, suggest


class TestMapDict(unittest.TestCase):
    def test_calls_function_for_each_pair(self):
        calls = []
        mapDict(lambda k, v: calls.append((k, v)), {"a": 1, "b": 2})
        self.assertEqual(sorted(calls), [("a", 1), ("b", 2)])

    def test_empty_dict(self):
        calls = []
        mapDict(lambda k, v: calls.append((k, v)), {})
        self.assertEqual(calls, [])


class TestCommonPrefix(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(commonPrefix([]), "")

    def test_single_completion_returns_suffix(self):
        self.assertEqual(commonPrefix([("ab", "abcdef")]), "cdef")

    def test_common_prefix_of_several(self):
        completions = [("", "abcx"), ("", "abcy"), ("", "abz")]
        self.assertEqual(commonPrefix(completions), "ab")

    def test_no_common_prefix(self):
        completions = [("", "abc"), ("", "xyz")]
        self.assertEqual(commonPrefix(completions), "")

    def test_prefix_longer_than_other_option(self):
        completions = [("", "abcdef"), ("", "ab")]
        self.assertEqual(commonPrefix(completions), "ab")


class TestSplitPath(unittest.TestCase):
    def test_no_separator(self):
        self.assertEqual(splitPath("abc"), ("abc", None))

    def test_with_separator(self):
        self.assertEqual(splitPath("abc/def/ghi"), ("abc", "def/ghi"))

    def test_custom_separator(self):
        self.assertEqual(splitPath("a:b", sep=":"), ("a", "b"))


class TestSuggest(unittest.TestCase):
    def test_prefix_matches(self):
        completions = suggest(["start", "stop", "status"], "sta")
        values = [c[1] for c in completions]
        self.assertIn("start", values)
        self.assertIn("status", values)
        self.assertNotIn("stop", values)

    def test_single_match_gets_trailing_space(self):
        completions = suggest(["unique", "other"], "uni")
        self.assertEqual(completions, [("uni", "unique ")])

    def test_exact_match_appends_space_option(self):
        completions = suggest(["back", "backup"], "back")
        self.assertIn(("back", "back "), completions)
        self.assertIn(("back", "backup"), completions)

    def test_skip_list_excludes_values(self):
        completions = suggest(["a", "ab", "abc"], "a", skipList=("ab",))
        values = [c[1] for c in completions]
        self.assertIn("abc", values)
        self.assertNotIn("ab", values)

    def test_no_match_is_empty(self):
        self.assertEqual(suggest(["start", "stop"], "zzz"), [])
