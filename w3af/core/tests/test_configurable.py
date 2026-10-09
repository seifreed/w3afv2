"""Tests for the core configurable contract."""

import unittest

from w3af.core.configurable import Configurable


class TestConfigurable(unittest.TestCase):
    def test_set_options_requires_an_implementation(self):
        with self.assertRaisesRegex(
            NotImplementedError,
            "Configurable object is not implementing required method set_options",
        ):
            Configurable().set_options(None)

    def test_get_options_requires_an_implementation(self):
        with self.assertRaisesRegex(
            NotImplementedError,
            "Configurable object is not implementing required method get_options",
        ):
            Configurable().get_options()

    def test_get_name_uses_the_concrete_class_name(self):
        self.assertEqual(Configurable().get_name(), "Configurable")

    def test_get_type_identifies_configurable_objects(self):
        self.assertEqual(Configurable().get_type(), "configurable")
