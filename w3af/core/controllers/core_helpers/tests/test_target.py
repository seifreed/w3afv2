"""
test_target.py

Copyright 2012 Andres Riancho

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

import os
import shutil
import tempfile
import unittest

import pytest

from w3af.core.controllers.core_helpers.target import CoreTarget
from w3af.core.data.kb.config import Config
from w3af.core.data.options.opt_factory import opt_factory
from w3af.core.data.options.option_list import OptionList
from w3af.core.data.options.option_types import (
    BOOL,
    COMBO,
    FLOAT,
    INPUT_FILE,
    INT,
    IPPORT,
    LIST,
    OUTPUT_FILE,
    PORT,
    REGEX,
    STRING,
    URL,
    URL_LIST,
)
from w3af.core.data.parsers.doc.url import URL as URL_KLASS
from w3af.core.exceptions import BaseFrameworkException

OPTION_TYPES = (
    BOOL,
    INT,
    FLOAT,
    STRING,
    URL,
    IPPORT,
    LIST,
    REGEX,
    COMBO,
    INPUT_FILE,
    OUTPUT_FILE,
    PORT,
    URL_LIST,
)


@pytest.mark.smoke
class TestTarget(unittest.TestCase):

    def test_basic(self):
        opt_lst = CoreTarget(cf).get_options()

        for opt in opt_lst:
            self.assertIn(opt.get_type(), OPTION_TYPES)
            self.assertTrue(opt.get_name())
            self.assertEqual(opt, opt)

            # Just verify that this doesn't crash and that the types
            # are correct
            self.assertIsInstance(opt.get_name(), str)
            self.assertIsInstance(opt.get_desc(), str)
            self.assertIsInstance(opt.get_type(), str)
            self.assertIsInstance(opt.get_help(), str)
            self.assertIsInstance(opt.get_value_str(), str)

    def test_configuration_is_injected(self):
        cf.save("targets", ["global"])
        injected_configuration = Config()

        CoreTarget(injected_configuration)

        self.assertEqual(injected_configuration.get("targets"), [])
        self.assertEqual(cf.get("targets"), ["global"])

    def test_verify_url(self):
        ctarget = CoreTarget(cf)

        self.assertRaises(
            BaseFrameworkException,
            ctarget._verify_url,
            URL_KLASS("ftp://www.google.com/"),
        )

        self.assertTrue(ctarget._verify_url(URL_KLASS("http://www.google.com/")))
        self.assertTrue(ctarget._verify_url(URL_KLASS("http://www.google.com:39/")))

    def test_verify_file_target(self):
        target_file = self.write_target_file(
            "http://127.0.0.1:8000/1\n"
            "\n"
            "# A comment line is ignored\n"
            "http://127.0.0.1:8000/2\n"
        )

        ctarget = self.set_target(f"file://{target_file}")

        self.assertEqual(
            cf.get("targets"),
            [
                URL_KLASS("http://127.0.0.1:8000/1"),
                URL_KLASS("http://127.0.0.1:8000/2"),
            ],
        )
        self.assertEqual(cf.get("target_domains"), ["127.0.0.1"])
        self.assertTrue(ctarget.has_valid_configuration())

    def test_missing_target_file(self):
        missing_file = os.path.join(self.make_temp_dir(), "missing.target")

        with self.assertRaisesRegex(BaseFrameworkException, "Cannot open target"):
            self.set_target(f"file://{missing_file}")

    def test_invalid_url_inside_target_file(self):
        target_file = self.write_target_file("http://\n")

        with self.assertRaisesRegex(BaseFrameworkException, "is invalid"):
            self.set_target(f"file://{target_file}")

    def test_file_url_inside_target_file_is_rejected(self):
        target_file = self.write_target_file("file:///etc/hosts\n")

        with self.assertRaisesRegex(BaseFrameworkException, "Invalid format"):
            self.set_target(f"file://{target_file}")

    def test_more_than_one_target_domain(self):
        with self.assertRaisesRegex(BaseFrameworkException, "more than one target"):
            self.set_target("http://127.0.0.1:8000/,http://localhost:8000/")

    def test_set_target_os_and_framework(self):
        ctarget = CoreTarget(cf)
        options = ctarget.get_options()
        options["target"].set_value("http://127.0.0.1:8000/")
        options["target_os"].set_value("unix")
        options["target_framework"].set_value("php")

        ctarget.set_options(options)

        self.assertEqual(cf.get("target_os"), "unix")
        self.assertEqual(cf.get("target_framework"), "php")
        self.assertEqual(ctarget.get_options()["target_os"].get_value_str(), "unix")

    def test_unknown_target_os(self):
        options = self.options_with("target_os", "solaris")

        with self.assertRaisesRegex(BaseFrameworkException, "operating system"):
            CoreTarget(cf).set_options(options)

    def test_unknown_target_framework(self):
        options = self.options_with("target_framework", "cobol")

        with self.assertRaisesRegex(BaseFrameworkException, "programming framework"):
            CoreTarget(cf).set_options(options)

    def test_name_description_and_empty_configuration(self):
        ctarget = CoreTarget(cf)

        self.assertEqual(ctarget.get_name(), "target_settings")
        self.assertEqual(ctarget.get_desc(), "Configure target URLs")
        self.assertFalse(ctarget.has_valid_configuration())

    def setUp(self):
        CoreTarget(cf).clear()
        self.addCleanup(CoreTarget(cf).clear)

    def make_temp_dir(self):
        temp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, temp_dir)
        return temp_dir

    def write_target_file(self, content):
        target_file = os.path.join(self.make_temp_dir(), "local.target")
        with open(target_file, "w", encoding="utf-8") as target_file_handler:
            target_file_handler.write(content)
        return target_file

    def set_target(self, target):
        ctarget = CoreTarget(cf)
        options = ctarget.get_options()
        options["target"].set_value(target)
        ctarget.set_options(options)
        return ctarget

    def options_with(self, combo_name, combo_value):
        """
        :return: The target options where the combo_name option only allows
                 combo_value, as an option list built outside CoreTarget would
        """
        options = OptionList()
        for option in CoreTarget(cf).get_options():
            if option.get_name() == combo_name:
                option = opt_factory(combo_name, [combo_value], "", "combo")
            options.add(option)

        options["target"].set_value("http://127.0.0.1:8000/")
        return options


cf = Config()
