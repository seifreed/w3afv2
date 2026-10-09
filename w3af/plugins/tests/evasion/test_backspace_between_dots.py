"""
test_backspace_between_dots.py

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

from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.url.http_request import HTTPRequest
from w3af.plugins.evasion.backspace_between_dots import backspace_between_dots


class TestEvasion(unittest.TestCase):
    """
    The URL class normalizes "/../" away when the URL is built, so the
    evasion never sees that sequence through a URL object. These tests assert
    the real behaviour: a new request is returned and the original URL is not
    modified.
    """

    def test_no_modification(self):
        plugin = backspace_between_dots()

        url = URL("http://www.w3af.com/")
        request = HTTPRequest(url)
        new_request = plugin.modify_request(request)

        self.assertEqual(new_request.url_object.url_string, "http://www.w3af.com/")
        self.assertIsNot(new_request, request)

    def test_normalized_path_with_filename(self):
        plugin = backspace_between_dots()

        url = URL("http://www.w3af.com/abc/def/.././jkl.htm")
        request = HTTPRequest(url)
        new_request = plugin.modify_request(request)

        self.assertEqual(
            new_request.url_object.url_string, "http://www.w3af.com/abc/./jkl.htm"
        )
        self.assertEqual(url.url_string, "http://www.w3af.com/abc/./jkl.htm")
