"""Validation behaviour of every option type, built through opt_factory."""

import os
import shutil
import stat
import tempfile
import unittest

from w3af.core.data.dc.headers import Headers
from w3af.core.data.dc.query_string import QueryString
from w3af.core.data.options.opt_factory import opt_factory
from w3af.core.data.options.option_list import OptionList
from w3af.core.data.options.option_types import (
    BOOL,
    COMBO,
    FORM_ID_LIST,
    HEADER,
    INPUT_FILE,
    IPPORT,
    LIST,
    OUTPUT_FILE,
    PORT,
    POSITIVE_INT,
    QUERY_STRING,
    STRING,
)
from w3af.core.data.parsers.utils.form_id_matcher_list import FormIDMatcherList
from w3af.core.exceptions import BaseFrameworkException


def option(_type, value, name="name"):
    return opt_factory(name, value, "desc", _type, "help", "tab")


class Unprintable:
    def __str__(self):
        raise ValueError("no string representation")


class TestBaseOption(unittest.TestCase):
    def test_accessors(self):
        opt = option(STRING, "abc")
        opt.set_value("def")

        self.assertEqual(opt.get_name(), "name")
        self.assertEqual(opt.get_desc(), "desc")
        self.assertEqual(opt.get_help(), "help")
        self.assertEqual(opt.get_tabid(), "tab")
        self.assertEqual(opt.get_type(), STRING)
        self.assertEqual(opt.get_default_value(), "abc")
        self.assertEqual(opt.get_value(), "def")
        self.assertEqual(opt.get_value_str(), "def")
        self.assertEqual(repr(opt), "<option name:name|type:string|value:def>")

    def test_equality(self):
        self.assertEqual(option(STRING, "abc"), option(STRING, "abc"))
        self.assertNotEqual(option(STRING, "abc"), option(STRING, "def"))
        self.assertNotEqual(option(STRING, "abc"), "abc")


class TestScalarOptions(unittest.TestCase):
    def test_bool(self):
        self.assertIs(option(BOOL, "TRUE").get_value(), True)
        self.assertIs(option(BOOL, "false").get_value(), False)
        self.assertRaises(BaseFrameworkException, option, BOOL, "yes")

    def test_string(self):
        self.assertEqual(option(STRING, 12).get_value(), "12")
        self.assertRaises(BaseFrameworkException, option, STRING, Unprintable())

    def test_port(self):
        self.assertEqual(option(PORT, "8080").get_value(), 8080)
        self.assertRaises(BaseFrameworkException, option, PORT, "http")
        self.assertRaises(BaseFrameworkException, option, PORT, "0")
        self.assertRaises(BaseFrameworkException, option, PORT, "65536")

    def test_positive_integer(self):
        self.assertEqual(option(POSITIVE_INT, "0").get_value(), 0)
        self.assertRaises(BaseFrameworkException, option, POSITIVE_INT, "one")
        self.assertRaises(BaseFrameworkException, option, POSITIVE_INT, "-1")

    def test_ipport(self):
        self.assertEqual(option(IPPORT, "127.0.0.1:80").get_value(), "127.0.0.1:80")

        for invalid in (
            "127.0.0.1",
            None,
            "localhost:80",
            "127.0.0.1:http",
            "127.0.0.1:0",
            "127.0.0.1:65536",
        ):
            with self.subTest(value=invalid):
                self.assertRaises(BaseFrameworkException, option, IPPORT, invalid)


class TestComboOption(unittest.TestCase):
    def test_default_is_first_choice(self):
        opt = option(COMBO, ["a", "b"])

        self.assertEqual(opt.get_value(), "a")
        self.assertEqual(opt.get_default_value(), "a")

    def test_set_value(self):
        opt = option(COMBO, ["a", "b"])
        opt.set_value("b")

        self.assertEqual(opt.get_value(), "b")
        self.assertRaises(BaseFrameworkException, opt.set_value, "c")


class TestListOption(unittest.TestCase):
    def test_parse(self):
        opt = option(LIST, "a, \"b c\",'d', ,e")

        self.assertEqual(opt.get_value(), ["a", "b c", "d", "e"])
        self.assertEqual(opt.get_value_str(), "a,b c,d,e")

    def test_list_value(self):
        self.assertEqual(option(LIST, ["a", 1]).get_value_str(), "a,1")

    def test_brackets_are_rejected(self):
        self.assertRaises(BaseFrameworkException, option, LIST, "[a,b]")

    def test_multiline_is_rejected(self):
        self.assertRaises(BaseFrameworkException, option, LIST, "a\nb")


class TestStructuredOptions(unittest.TestCase):
    def test_header_instance(self):
        headers = Headers([("A", "b")])

        self.assertIs(option(HEADER, headers).get_value(), headers)

    def test_header_string(self):
        self.assertEqual(option(HEADER, "A: b\r\n").get_value(), Headers([("A", "b")]))

    def test_invalid_header(self):
        self.assertRaises(BaseFrameworkException, option, HEADER, None)

    def test_query_string_instance(self):
        query_string = QueryString([("a", ["1"])])

        self.assertIs(option(QUERY_STRING, query_string).get_value(), query_string)

    def test_form_id_list_instance(self):
        form_ids = FormIDMatcherList('[{"action": "/foo"}]')

        opt = option(FORM_ID_LIST, form_ids)

        self.assertEqual(opt.get_value_for_profile(), '[{"action": "/foo"}]')


class TestOutputFileOption(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.directory)

    def test_dev_null(self):
        self.assertEqual(option(OUTPUT_FILE, "/dev/null").get_value(), "/dev/null")

    def test_random_suffix(self):
        value = option(OUTPUT_FILE, os.path.join(self.directory, "$rnd$.txt"))

        self.assertNotIn("$rnd$", value.get_value())
        self.assertTrue(value.get_value().startswith(self.directory))

    def test_directory_is_rejected(self):
        self.assertRaises(BaseFrameworkException, option, OUTPUT_FILE, self.directory)

    def test_missing_directory(self):
        missing = os.path.join(self.directory, "missing", "out.txt")

        self.assertRaises(BaseFrameworkException, option, OUTPUT_FILE, missing)

    def test_read_only_directory(self):
        read_only = os.path.join(self.directory, "ro")
        os.mkdir(read_only, stat.S_IRUSR | stat.S_IXUSR)
        self.addCleanup(os.chmod, read_only, stat.S_IRWXU)

        self.assertRaises(
            BaseFrameworkException,
            option,
            OUTPUT_FILE,
            os.path.join(read_only, "out.txt"),
        )

    def test_read_only_file(self):
        read_only = os.path.join(self.directory, "out.txt")
        with open(read_only, "w") as output:
            output.write("x")
        os.chmod(read_only, stat.S_IRUSR)

        self.assertRaises(BaseFrameworkException, option, OUTPUT_FILE, read_only)

    def test_empty_value(self):
        self.assertRaises(BaseFrameworkException, option, OUTPUT_FILE, "")


class TestInputFilePermissions(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.directory)

    def test_unreadable_directory(self):
        unreadable = os.path.join(self.directory, "locked")
        os.mkdir(unreadable, stat.S_IWUSR | stat.S_IXUSR)
        self.addCleanup(os.chmod, unreadable, stat.S_IRWXU)

        self.assertRaises(
            BaseFrameworkException,
            option,
            INPUT_FILE,
            os.path.join(unreadable, "in.txt"),
        )

    def test_unreadable_file(self):
        unreadable = os.path.join(self.directory, "in.txt")
        with open(unreadable, "w") as input_file:
            input_file.write("x")
        os.chmod(unreadable, stat.S_IWUSR)

        self.assertRaises(BaseFrameworkException, option, INPUT_FILE, unreadable)


class TestOptionList(unittest.TestCase):
    def setUp(self):
        self.options = OptionList()
        self.options.add(option(STRING, "a", name="first"))
        self.options.append(option(BOOL, "true", name="second"))

    def test_lookup(self):
        self.assertEqual(len(self.options), 2)
        self.assertIn("first", self.options)
        self.assertNotIn("third", self.options)
        self.assertEqual(self.options["second"].get_value(), True)
        self.assertEqual(self.options[0].get_name(), "first")
        self.assertEqual(self.options["1"].get_name(), "second")

    def test_missing_option(self):
        self.assertRaises(BaseFrameworkException, self.options.__getitem__, "third")

    def test_repr(self):
        self.assertEqual(repr(self.options), "<OptionList: first|second>")

    def test_equality(self):
        other = OptionList()
        other.add(option(STRING, "a", name="first"))
        other.add(option(BOOL, "true", name="second"))

        self.assertEqual(self.options, other)
        self.assertNotEqual(self.options, OptionList())
        self.assertNotEqual(self.options, ["first", "second"])
