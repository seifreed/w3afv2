import unittest

from w3af.core.data.misc.iterables import (
    unique_everseen,
    unique_everseen_hash,
    unique_justseen,
)


class TestIterableHelpers(unittest.TestCase):

    def test_unique_everseen_preserves_first_occurrence(self):
        self.assertEqual(list(unique_everseen("AAAABBBCCDAABBB")), list("ABCD"))

    def test_unique_everseen_supports_a_key(self):
        values = ["one", "two", "ONE"]

        self.assertEqual(list(unique_everseen(values, str.lower)), ["one", "two"])

    def test_unique_justseen_removes_consecutive_duplicates(self):
        expected = ["A", "B", "C", "D", "A", "B"]

        self.assertEqual(list(unique_justseen("AAAABBBCCDAABBB")), expected)

    def test_unique_justseen_supports_a_key(self):
        values = ["A", "a", "B", "b", "A"]

        self.assertEqual(list(unique_justseen(values, str.lower)), ["A", "B", "A"])

    def test_unique_everseen_hash_preserves_first_occurrence(self):
        values = ["first", "second", "first"]

        self.assertEqual(list(unique_everseen_hash(values)), ["first", "second"])
