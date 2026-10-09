"""Tests for the serialized-object heuristics used by the deserialization plugins."""

import unittest

from w3af.core.data.serialization.detect import (
    is_java_serialized_data,
    is_net_serialized_data,
    is_nodejs_serialized_data,
    is_pickled_data,
)

# The protocol 0 serialization of {"a": 1} produced by Python's pickle module.
PROTOCOL_ZERO_DICT = "(dp0\nVa\np1\nI1\ns."


class TestIsPickledData(unittest.TestCase):
    def test_protocol_zero_payload(self):
        self.assertTrue(is_pickled_data(PROTOCOL_ZERO_DICT))

    def test_many_lines(self):
        self.assertTrue(is_pickled_data("x\n" * 11))

    def test_plain_text(self):
        self.assertFalse(is_pickled_data("hello world"))


class TestIsJavaSerializedData(unittest.TestCase):
    def test_binary_with_java_class(self):
        data = "\xac\xed\x00\x05sr\x00java.util.HashMap"
        self.assertTrue(is_java_serialized_data(data))

    def test_binary_without_java_class(self):
        self.assertFalse(is_java_serialized_data("\xac\xed\x00\x05sr\x00foo"))

    def test_printable_data_is_not_serialized(self):
        self.assertFalse(is_java_serialized_data("java.util.HashMap"))


class TestIsNodeJSSerializedData(unittest.TestCase):
    def test_function_body(self):
        data = '{"rce":"_$$ND_FUNC$$_function (){}"}'
        self.assertTrue(is_nodejs_serialized_data(data))

    def test_plain_word(self):
        self.assertFalse(is_nodejs_serialized_data("hello"))


class TestIsNetSerializedData(unittest.TestCase):
    def test_type_marker(self):
        self.assertTrue(is_net_serialized_data('{"$type":"System.Windows.Data"}'))

    def test_plain_word(self):
        self.assertFalse(is_net_serialized_data("hello"))
