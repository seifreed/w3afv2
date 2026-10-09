"""
test_evasion_plugins.py

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
from w3af.plugins import evasion
from w3af.plugins.evasion.backspace_between_dots import backspace_between_dots
from w3af.plugins.evasion.full_width_encode import full_width_encode
from w3af.plugins.evasion.mod_security import mod_security
from w3af.plugins.evasion.reversed_slashes import reversed_slashes
from w3af.plugins.evasion.rnd_case import rnd_case
from w3af.plugins.evasion.rnd_hex_encode import rnd_hex_encode
from w3af.plugins.evasion.rnd_param import rnd_param
from w3af.plugins.evasion.rnd_path import rnd_path
from w3af.plugins.evasion.self_reference import self_reference
from w3af.plugins.evasion.shift_out_in_between_dots import shift_out_in_between_dots
from w3af.plugins.evasion.x_forwarded_for import x_forwarded_for

ALL_EVASION_PLUGINS = (
    backspace_between_dots,
    full_width_encode,
    mod_security,
    reversed_slashes,
    rnd_case,
    rnd_hex_encode,
    rnd_param,
    rnd_path,
    self_reference,
    shift_out_in_between_dots,
    x_forwarded_for,
)


class TestEvasionPluginMetadata(unittest.TestCase):

    def test_priority_is_in_range(self):
        for klass in ALL_EVASION_PLUGINS:
            with self.subTest(plugin=klass.__name__):
                self.assertIn(klass().get_priority(), range(101))

    def test_long_desc(self):
        for klass in ALL_EVASION_PLUGINS:
            with self.subTest(plugin=klass.__name__):
                self.assertTrue(klass().get_long_desc().strip())

    def test_package_long_description(self):
        self.assertTrue(evasion.get_long_description().strip())


class TestFullWidthEncodePostData(unittest.TestCase):

    def test_encode_post_data(self):
        request = HTTPRequest(URL("http://www.w3af.com/"), data="a=b")

        modified_data = full_width_encode().modify_request(request).get_data()

        self.assertEqual(modified_data, "%uFF41=%uFF42")
