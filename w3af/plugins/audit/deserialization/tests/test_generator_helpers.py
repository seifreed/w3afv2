"""Tests for deserialization generator helpers."""

import unittest

from w3af.plugins.audit.deserialization_generator_helpers import (
    find_payload_offsets,
)


class TestGeneratorHelpers(unittest.TestCase):
    def test_find_payload_offsets(self):
        offsets = find_payload_offsets("prefix1suffix", "prefix3suffix", "1", "3", 1)

        self.assertEqual(offsets, [6])
