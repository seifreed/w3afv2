"""
test_response_cut.py

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
from unittest import SkipTest

import pytest

from w3af.core.data.misc.response_cut import ResponseCutMixin
from w3af.core.exceptions import BodyCutException


class TestResponseCutMixin(unittest.TestCase):

    def setUp(self):
        self.cam = ResponseCutMixin()

    def test_cut_rejects_lengths_larger_than_body(self):
        self.cam.set_cut(4, 3)

        with self.assertRaises(BodyCutException):
            self.cam._cut("short")

    def test_cut_requires_configured_lengths(self):
        with self.assertRaises(RuntimeError):
            self.cam._cut("body")

    def test_cut_returns_empty_body(self):
        self.cam.set_cut(0, 0)

        self.assertEqual(self.cam._cut(""), "")

    def test_define_exact_cut_rejects_missing_expected_result(self):
        self.assertFalse(self.cam._define_exact_cut("body", "missing"))

    def test_guess_cut_rejects_missing_expected_result(self):
        self.assertFalse(self.cam._guess_cut("body", "other", "missing"))

    def test_guess_cut_rejects_identical_bodies(self):
        self.assertFalse(self.cam._guess_cut("same", "same", "same"))

    def test_guess_cut_uses_matching_header_and_footer(self):
        expected = "expected"
        body_a = ["header--", expected, "footer1", "footer2", "footer3"]
        body_b = ["header--", "different", "footer1", "footer2", "footer3"]

        self.assertTrue(self.cam._guess_cut(body_a, body_b, expected))
        self.assertEqual((self.cam._header_length, self.cam._footer_length), (1, 3))

    def test_guess_cut_with_sequence_without_header(self):
        body_a = ["expected", "footer1", "footer2"]
        body_b = ["different", "footer1", "footer2"]

        self.assertTrue(self.cam._guess_cut(body_a, body_b, "expected"))
        self.assertEqual((self.cam._header_length, self.cam._footer_length), (0, 2))

    def test_etc_passwd_extract_basic(self):
        body = """HEADER
                  root:x:0:0:root:/root:/bin/bash
                  daemon:x:1:1:daemon:/usr/sbin:/bin/sh
                  bin:x:2:2:bin:/bin:/bin/sh
                  FOOTER123"""
        self.cam._define_cut_from_etc_passwd(body, body)

        header = "HEADER\n                  "
        footer = "                  FOOTER123"
        self.assertEqual(self.cam._header_length, len(header))
        self.assertEqual(self.cam._footer_length, len(footer))

        mtab_content = """/dev/sda1 / ext4 rw,errors=remount-ro 0 0
                          proc /proc proc rw,noexec,nosuid,nodev 0 0
                          sysfs /sys sysfs rw,noexec,nosuid,nodev 0 0
                          none /sys/fs/fuse/connections fusectl rw 0 0"""
        mtab_body = f"{header}{mtab_content}{footer}"
        self.assertEqual(self.cam._cut(mtab_body), mtab_content)

    def test_etc_passwd_extract_div(self):
        body = """<div>root:x:0:0:root:/root:/bin/bash
                  daemon:x:1:1:daemon:/usr/sbin:/bin/sh
                  bin:x:2:2:bin:/bin:/bin/sh\n</div>"""
        self.cam._define_cut_from_etc_passwd(body, body)

        self.assertEqual(self.cam._header_length, len("<div>"))
        self.assertEqual(self.cam._footer_length, len("</div>"))

    def test_etc_passwd_extract_no_header_footer(self):
        body = """root:x:0:0:root:/root:/bin/bash
                  daemon:x:1:1:daemon:/usr/sbin:/bin/sh
                  bin:x:2:2:bin:/bin:/bin/sh\n"""
        self.cam._define_cut_from_etc_passwd(body, body)

        self.assertEqual(self.cam._header_length, len(""))
        self.assertEqual(self.cam._footer_length, len(""))

    def test_etc_passwd_extract_together(self):
        body = """HEADERroot:x:0:0:root:/root:/bin/bash
                  daemon:x:1:1:daemon:/usr/sbin:/bin/sh
                  bin:x:2:2:bin:/bin:/bin/sh\nFOOTER"""
        self.cam._define_cut_from_etc_passwd(body, body)
        self.assertEqual(self.cam._header_length, len("HEADER"))
        self.assertEqual(self.cam._footer_length, len("FOOTER"))

    def test_etc_passwd_extract_bad_1(self):
        self.assertRaises(ValueError, self.cam._define_cut_from_etc_passwd, "a", "b")

    def test_etc_passwd_extract_bad_2(self):
        self.assertRaises(ValueError, self.cam._define_cut_from_etc_passwd, "a", "a")

    def test_etc_passwd_extract_bad_3(self):
        body = """HEADER
                  andres:x:0:0:andres:/andres:/bin/bash
                  daemon:x:1:1:daemon:/usr/sbin:/bin/sh
                  bin:x:2:2:bin:/bin:/bin/sh
                  FOOTER123"""
        self.assertRaises(ValueError, self.cam._define_cut_from_etc_passwd, body, body)

    def test_etc_passwd_extract_bad_4(self):
        body = """HEADERroot:x:0:0:root:/root:/bin/bash
                  daemon:x:1:1:daemon:/usr/sbin:/bin/sh
                  bin:x:2:2:bin:/bin:/bin/shFOOTER"""
        self.assertRaises(ValueError, self.cam._define_cut_from_etc_passwd, body, body)

    def test_define_exact_cut_basic(self):
        expected = "w3af\n"
        header = "HEADER"
        footer = "FOOTER123"
        body = f"{header}{expected}{footer}"
        self.cam._define_exact_cut(body, expected)

        self.assertEqual(self.cam._header_length, len(header))
        self.assertEqual(self.cam._footer_length, len(footer))

        another_content = """hello world"""
        another_body = f"{header}{another_content}{footer}"
        self.assertEqual(self.cam._cut(another_body), another_content)

    def test_guess_cut_basic(self):
        expected = "w3af\n"
        error = "error found while trying to read not existing file"
        header = "HEADER"
        footer = "FOOTER123"

        body_a = f"{header}{expected}{footer}"
        body_b = f"{header}{error}{footer}"

        self.cam._guess_cut(body_a, body_b, expected)

        self.assertEqual(self.cam._header_length, len(header))
        self.assertEqual(self.cam._footer_length, len(footer))

        another_content = """hello world"""
        another_body = f"{header}{another_content}{footer}"
        self.assertEqual(self.cam._cut(another_body), another_content)

    @pytest.mark.ci_fails
    def test_guess_cut_no_header(self):
        raise SkipTest("string response without a header remains unsupported")

    def test_guess_cut_no_footer(self):
        expected = "w3af\n"
        error = "error found while trying to read not existing file"
        header = "HEADER"
        footer = ""

        body_a = f"{header}{expected}{footer}"
        body_b = f"{header}{error}{footer}"

        self.cam._guess_cut(body_a, body_b, expected)

        self.assertEqual(self.cam._header_length, len(header))
        self.assertEqual(self.cam._footer_length, len(footer))

        another_content = """hello world"""
        another_body = f"{header}{another_content}{footer}"
        self.assertEqual(self.cam._cut(another_body), another_content)

    def test_guess_cut_no_header_no_footer(self):
        expected = "w3af\n"
        error = "error found while trying to read not existing file"
        header = ""
        footer = ""

        body_a = f"{header}{expected}{footer}"
        body_b = f"{header}{error}{footer}"

        self.cam._guess_cut(body_a, body_b, expected)

        self.assertEqual(self.cam._header_length, len(header))
        self.assertEqual(self.cam._footer_length, len(footer))

        another_content = """hello world"""
        another_body = f"{header}{another_content}{footer}"
        self.assertEqual(self.cam._cut(another_body), another_content)
