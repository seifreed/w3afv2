"""
test_io.py

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

import unittest

from w3af.core.data.misc.io import NamedStringIO, is_file_like


class TestIO(unittest.TestCase):

    def test_named_string_io(self):
        content = "content"
        name = "name"
        ns_io = NamedStringIO(content, name)
        self.assertEqual(str(ns_io), content)
        self.assertEqual(ns_io.read(), content)
        self.assertEqual(ns_io.name, name)
        self.assertFalse(ns_io.closed)

    def test_named_string_io_supports_seek_and_write(self):
        stream = NamedStringIO("content", "name")
        stream.seek(0)
        stream.write("new")
        stream.seek(0)
        self.assertEqual(stream.read(), "newtent")

    def test_named_string_io_is_file_like(self):
        self.assertTrue(is_file_like(NamedStringIO("content", "name")))

    def test_string_is_not_file_like(self):
        self.assertFalse(is_file_like("content"))
