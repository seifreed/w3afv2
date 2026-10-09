"""
test_encoding.py

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

import unittest

from w3af.core.data.misc.encoding import (
    ESCAPED_CHAR,
    HTML_ENCODE,
    PERCENT_ENCODE,
    is_known_encoding,
    smart_str,
    smart_str_ignore,
    smart_unicode,
)


class UnprintableObject:
    def __str__(self):
        raise UnicodeEncodeError("ascii", "\xff", 0, 1, "cannot be printed")


class TestEncoding(unittest.TestCase):

    def test_is_known_encoding_true(self):
        self.assertTrue(is_known_encoding("utf-8"))

    def test_is_known_encoding_false(self):
        self.assertFalse(is_known_encoding("andres-16"))

    def test_escaped_char_empty(self):
        decoded = b"".decode("utf-8", errors=ESCAPED_CHAR)
        self.assertEqual(decoded, "")

    def test_escaped_char_no_error(self):
        decoded = "ábc".encode().decode("utf-8", errors=ESCAPED_CHAR)
        self.assertEqual(decoded, "ábc")

    def test_escaped_char_error_escape_char(self):
        decoded = b"\xff".decode("utf-8", errors=ESCAPED_CHAR)
        self.assertEqual(decoded, "\\xff")

    def test_escaped_char_error_html_encode(self):
        decoded = b"\xff".decode("utf-8", errors=HTML_ENCODE)
        self.assertEqual(decoded, "&#xff")

    def test_atilde(self):
        self.assertEqual(smart_unicode("á"), "á")

    def test_smart_unicode_decodes_bytes(self):
        self.assertEqual(smart_unicode("á".encode()), "á")

    def test_smart_str_preserves_bytes(self):
        value = b"\x00\xff"
        self.assertIs(smart_str(value), value)

    def test_escaped_char_encode_error(self):
        self.assertEqual("a\xff".encode("ascii", errors=ESCAPED_CHAR), b"a\\xff")
        self.assertEqual("\u4e2d".encode("ascii", errors=ESCAPED_CHAR), b"\\u4e2d")

    def test_html_encode_encode_error(self):
        self.assertEqual("a\xff".encode("ascii", errors=HTML_ENCODE), b"a&#xff")

    def test_percent_encode_encode_error(self):
        self.assertEqual("a\xe1".encode("ascii", errors=PERCENT_ENCODE), b"a%C3%A1")

    def test_percent_encode_only_handles_encode_errors(self):
        self.assertRaises(
            UnicodeDecodeError, b"\xff".decode, "ascii", errors=PERCENT_ENCODE
        )

    def test_smart_unicode_object(self):
        self.assertEqual(smart_unicode(12), "12")

    def test_smart_unicode_without_guessing(self):
        self.assertRaises(
            UnicodeDecodeError, smart_unicode, b"\xff", on_error_guess=False
        )

    def test_smart_unicode_guesses_encoding(self):
        self.assertEqual(smart_unicode(b"\xff"), "\xff")

    def test_smart_unicode_guess_fails(self):
        # chardet guesses UTF-16, which cannot decode an odd number of bytes
        self.assertEqual(smart_unicode(b"\xff\xfe\xfd"), "")

    def test_smart_unicode_no_guess(self):
        # chardet can not guess an encoding for these bytes
        self.assertEqual(smart_unicode(b"\x80\x00"), "\x00")

    def test_smart_str_encodes_text(self):
        self.assertEqual(smart_str("á"), "á".encode())

    def test_smart_str_converts_objects_to_bytes(self):
        self.assertEqual(smart_str(12), b"12")

    def test_smart_str_unprintable_object(self):
        self.assertRaises(UnicodeEncodeError, smart_str, UnprintableObject())
        self.assertEqual(smart_str_ignore(UnprintableObject()), b"")
