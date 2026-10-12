"""Tests for shared payload helpers."""

import unittest

from w3af.plugins.attack.payloads.payload_utils import int_to_dotted_quad


class TestPayloadUtils(unittest.TestCase):
    def test_int_to_dotted_quad(self):
        self.assertEqual(int_to_dotted_quad(0), "0.0.0.0")
        self.assertEqual(int_to_dotted_quad(0x0A000202), "10.0.2.2")
        self.assertEqual(int_to_dotted_quad(0xFFFFFFFF), "255.255.255.255")
