"""Tests for base64 detection of values seen in web applications."""

import base64
import unittest

from w3af.core.data.misc.base64_nopadding import maybe_decode_base64


class TestMaybeDecodeBase64(unittest.TestCase):
    def test_decodes_text(self):
        encoded = base64.b64encode(b"java.util.HashMap\xac\xed").decode("ascii")

        self.assertEqual(
            maybe_decode_base64(encoded), (True, "java.util.HashMap\xac\xed")
        )

    def test_decodes_bytes_to_bytes(self):
        encoded = base64.b64encode(b"java.util.HashMap\xac\xed")

        self.assertEqual(
            maybe_decode_base64(encoded), (True, b"java.util.HashMap\xac\xed")
        )

    def test_non_ascii_bytes_are_not_base64(self):
        self.assertEqual(maybe_decode_base64(b"\xff" * 16), (False, None))

    def test_short_strings_are_ignored(self):
        self.assertEqual(maybe_decode_base64("YWJj"), (False, None))

    def test_non_base64_alphabet(self):
        self.assertEqual(maybe_decode_base64("this is not base64!!"), (False, None))
