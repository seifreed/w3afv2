"""Tests for the input validation done when building quick matchers."""

import unittest

from w3af.core.data.quick_match.multi_in import MultiIn
from w3af.core.data.quick_match.multi_re import MultiRE


class TestMultiInInvalidInput(unittest.TestCase):
    def test_duplicated_keyword(self):
        self.assertRaises(ValueError, MultiIn, [("abc", 1), ("abc", 2)])

    def test_unsupported_item(self):
        self.assertRaises(TypeError, MultiIn, [1])


class TestMultiREInvalidInput(unittest.TestCase):
    def test_duplicated_regex(self):
        self.assertRaises(ValueError, MultiRE, [("abc", 1), ("abc", 2)])

    def test_unsupported_item(self):
        self.assertRaises(TypeError, MultiRE, [1])


class TestMultiREWithoutPrematchers(unittest.TestCase):
    def test_regexes_without_literal_hints_are_always_run(self):
        # Neither alternations nor back-references yield literal prematchers
        multi_re = MultiRE(["foobar", "a|b", r"(x)\1"])

        matched = {regex for _, regex in [m[:2] for m in multi_re.query("xx")]}
        self.assertEqual(matched, {r"(x)\1"})
