"""
test_input_file_option.py

Copyright 2015 Andres Riancho

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

import base64
import os
import tempfile
import textwrap
import unittest
import zlib

from w3af import ROOT_PATH
from w3af.core.data.options.input_file_option import InputFileOption
from w3af.core.data.options.opt_factory import opt_factory
from w3af.core.data.options.option_types import INPUT_FILE
from w3af.core.exceptions import BaseFrameworkException
from w3af.core.filesystem import (
    create_temp_dir,
    get_temp_dir,
    remove_temp_dir,
)


class TestInputFileOption(unittest.TestCase):

    INPUT_FILE = os.path.relpath(
        os.path.join(ROOT_PATH, "core", "data", "options", "tests", "test.txt")
    )

    def setUp(self):
        create_temp_dir()

    def tearDown(self):
        remove_temp_dir()

    def test_valid_base64_data(self):
        value = "%s%s" % (
            InputFileOption.DATA_PROTO,
            base64.b64encode(zlib.compress(b"xyz")).decode("ascii"),
        )
        opt = opt_factory("name", value, "desc", INPUT_FILE, "help", "tab")

        self.assertEqual(opt.get_value_for_profile(), value)
        with open(opt.get_value(), "rb") as input_file:
            self.assertEqual(input_file.read(), b"xyz")

        self.assertEqual(opt.get_default_value(), opt.get_value())

        self.assertEqual(os.path.dirname(opt.get_value()), get_temp_dir())
        self.assertIn(InputFileOption.DATA_PREFIX, opt.get_value())
        self.assertIn(InputFileOption.DATA_SUFFIX, opt.get_value())

        # Cleanup
        os.unlink(opt.get_value())

    def test_valid_wrapped_base64_data(self):
        content = bytes(range(256))
        encoded_data = base64.b64encode(zlib.compress(content)).decode("ascii")
        wrapped_data = "\n".join(textwrap.wrap(encoded_data, 76))
        value = "%s%s" % (InputFileOption.DATA_PROTO, wrapped_data)
        opt = opt_factory("name", value, "desc", INPUT_FILE, "help", "tab")
        try:
            with open(opt.get_value(), "rb") as input_file:
                self.assertEqual(input_file.read(), content)
        finally:
            os.unlink(opt.get_value())

    def test_invalid_base64_data(self):
        value = "%s%s" % (InputFileOption.DATA_PROTO, "x")
        self.assertRaises(
            BaseFrameworkException,
            opt_factory,
            "name",
            value,
            "desc",
            INPUT_FILE,
            "help",
            "tab",
        )

    def test_invalid_compressed_data(self):
        value = "%s%s" % (
            InputFileOption.DATA_PROTO,
            base64.b64encode(b"not compressed data").decode("ascii"),
        )
        with self.assertRaises(BaseFrameworkException):
            opt_factory("name", value, "desc", INPUT_FILE, "help", "tab")

    def test_empty_value(self):
        opt = opt_factory("name", "", "desc", INPUT_FILE, "help", "tab")
        self.assertEqual(opt.get_value(), "")
        self.assertEqual(opt.get_value_for_profile(), "")

    def test_invalid_directory(self):
        with self.assertRaises(BaseFrameworkException):
            opt_factory(
                "name",
                os.path.join("missing-directory", "file"),
                "desc",
                INPUT_FILE,
                "help",
                "tab",
            )

    def test_missing_file(self):
        missing_file = os.path.join(os.path.dirname(self.INPUT_FILE), "missing.txt")
        with self.assertRaises(BaseFrameworkException):
            opt_factory("name", missing_file, "desc", INPUT_FILE, "help", "tab")

    def test_directory_is_not_file(self):
        with self.assertRaises(BaseFrameworkException):
            opt_factory(
                "name",
                os.path.dirname(self.INPUT_FILE),
                "desc",
                INPUT_FILE,
                "help",
                "tab",
            )

    def test_profile_path_replaces_root_path(self):
        opt = opt_factory("name", self.INPUT_FILE, "desc", INPUT_FILE, "help", "tab")
        self.assertIn("%ROOT_PATH%", opt.get_value_for_profile())

    def test_encoding_failure_is_reported(self):
        with tempfile.NamedTemporaryFile(delete=False) as input_file:
            input_file.write(b"file data")
            filename = input_file.name
        try:
            opt = opt_factory("name", filename, "desc", INPUT_FILE, "help", "tab")
            os.unlink(filename)
            with self.assertRaises(BaseFrameworkException):
                opt.get_value_for_profile(self_contained=True)
        finally:
            if os.path.exists(filename):
                os.unlink(filename)

    def test_save_file_as_self_contained(self):
        opt = opt_factory("name", self.INPUT_FILE, "desc", INPUT_FILE, "help", "tab")

        encoded_value = opt.get_value_for_profile(self_contained=True)
        self.assertTrue(encoded_value.startswith(InputFileOption.DATA_PROTO))
        round_trip = zlib.decompress(
            base64.b64decode(encoded_value.removeprefix(InputFileOption.DATA_PROTO))
        )
        with open(self.INPUT_FILE, "rb") as input_file:
            self.assertEqual(round_trip, input_file.read())

    def test_relative_path(self):
        opt = opt_factory("name", self.INPUT_FILE, "desc", INPUT_FILE, "help", "tab")

        self.assertEqual(opt.get_value(), self.INPUT_FILE)

    def test_relative_path_full_path_input(self):
        full_path = os.path.join(
            ROOT_PATH, "core", "data", "options", "tests", "test.txt"
        )

        relative_path = os.path.relpath(full_path)

        opt = opt_factory("name", full_path, "desc", INPUT_FILE, "help", "tab")

        self.assertEqual(opt.get_value(), relative_path)

    def test_relative_path_when_cwd_is_root(self):
        # Change the CWD to root
        old_cwd = os.getcwd()
        os.chdir(os.path.abspath(os.sep))

        full_path = os.path.join(
            ROOT_PATH, "core", "data", "options", "tests", "test.txt"
        )

        relative_path = os.path.relpath(full_path)

        opt = opt_factory("name", full_path, "desc", INPUT_FILE, "help", "tab")

        self.assertEqual(opt.get_value(), relative_path)

        # Restore the previous CWD
        os.chdir(old_cwd)
