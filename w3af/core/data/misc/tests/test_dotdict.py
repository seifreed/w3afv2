"""Tests for the attribute-access dictionary used by the XML output plugin."""

import unittest

from w3af.core.data.misc.dotdict import dotdict


class TestDotDict(unittest.TestCase):
    def test_attribute_access(self):
        context = dotdict({"a": 1})
        context.b = "text"
        context.c = [1, 2]

        self.assertEqual(context.a, 1)
        self.assertEqual(context["b"], "text")
        self.assertEqual(context.c, [1, 2])
        self.assertIsNone(context.missing)

    def test_attribute_delete(self):
        context = dotdict({"a": 1})
        del context.a

        self.assertNotIn("a", context)
