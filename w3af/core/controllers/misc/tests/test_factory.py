"""
test_factory.py

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

from w3af.core.controllers.exceptions import BaseFrameworkException
from w3af.core.controllers.misc.factory import factory

FIXTURES = "w3af.core.controllers.misc.tests.factory_fixtures"


class TestFactory(unittest.TestCase):
    def test_creates_instance_with_arguments(self):
        instance = factory(f"{FIXTURES}.greeter", "w3af")

        self.assertEqual(type(instance).__name__, "greeter")
        self.assertEqual(instance.name, "w3af")

    def test_creates_real_plugin(self):
        spider = factory("w3af.plugins.crawl.web_spider")

        self.assertEqual(spider.get_name(), "web_spider")

    def test_missing_module(self):
        with self.assertRaisesRegex(BaseFrameworkException, "does not exist"):
            factory(f"{FIXTURES}.no_such_plugin")

    def test_syntax_error_is_propagated(self):
        self.assertRaises(SyntaxError, factory, f"{FIXTURES}.raises_syntax_error")

    def test_import_error_is_propagated(self):
        self.assertRaises(ImportError, factory, f"{FIXTURES}.raises_import_error")

    def test_other_import_time_errors_are_wrapped(self):
        with self.assertRaisesRegex(
            BaseFrameworkException, "plugin module failed to load"
        ):
            factory(f"{FIXTURES}.raises_runtime_error")

    def test_module_without_class(self):
        with self.assertRaisesRegex(BaseFrameworkException, "expected format"):
            factory(f"{FIXTURES}.without_class")

    def test_class_which_fails_to_instantiate(self):
        with self.assertRaisesRegex(BaseFrameworkException, "can not create plugin"):
            factory(f"{FIXTURES}.failing_init")
