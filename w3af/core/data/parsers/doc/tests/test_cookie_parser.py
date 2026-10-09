"""
test_cookie_parser.py

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

import http.cookies
import unittest

from w3af.core.data.parsers.doc.cookie_parser import parse_cookie


class TestParseCookie(unittest.TestCase):
    def test_basic(self):
        cookie = parse_cookie("abc=def")
        self.assertIn("abc", cookie)

    def test_with_path(self):
        cookie = parse_cookie("abc=def; path=/x")
        self.assertEqual(cookie["abc"]["path"], "/x")

    def test_invalid_cookie_raises(self):
        self.assertRaises(http.cookies.CookieError, parse_cookie, 'a"b=1')

    def test_empty_value_is_not_invalid(self):
        self.assertEqual(len(parse_cookie("")), 0)
