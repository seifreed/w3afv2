"""
test_serialization.py

Copyright 2026 w3af contributors

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

import os
import unittest

from w3af.core.data.parsers.doc.sgml import Tag
from w3af.core.data.parsers.ipc.serialization import (
    DeserializationError,
    get_temp_file,
    load_http_response_from_temp_file,
    load_object_from_temp_file,
    load_tags_from_temp_file,
    remove_file_if_exists,
    write_http_response_to_temp_file,
    write_object_to_temp_file,
    write_tags_to_temp_file,
)
from w3af.core.data.parsers.tests.test_document_parser import _build_http_response


class TestSerialization(unittest.TestCase):

    def test_http_response_round_trip(self):
        response = _build_http_response("<html>hello</html>", "text/html")

        filename = write_http_response_to_temp_file(response)
        loaded = load_http_response_from_temp_file(filename)

        self.assertEqual(loaded.get_body(), "<html>hello</html>")
        self.assertEqual(loaded.get_url(), response.get_url())
        self.assertFalse(os.path.exists(filename))

    def test_tags_round_trip_keeping_the_file(self):
        tags = [Tag("a", {"href": "/x"}, "x"), Tag("b", {}, None)]

        filename = write_tags_to_temp_file(tags)
        self.addCleanup(remove_file_if_exists, filename)

        self.assertEqual(load_tags_from_temp_file(filename, remove=False), tags)
        self.assertTrue(os.path.exists(filename))

    def test_object_round_trip(self):
        filename = write_object_to_temp_file({"key": [1, 2, 3]})

        self.assertEqual(load_object_from_temp_file(filename), {"key": [1, 2, 3]})
        self.assertFalse(os.path.exists(filename))

    def test_corrupt_file_raises_and_is_removed(self):
        with get_temp_file("corrupt") as temp:
            temp.write(b"this is not serialized data")

        with self.assertRaises(DeserializationError) as context:
            load_object_from_temp_file(temp.name)

        self.assertIn("Failed to deserialize", str(context.exception))
        self.assertFalse(os.path.exists(temp.name))

    def test_missing_file_raises(self):
        filename = write_tags_to_temp_file([])
        os.remove(filename)

        self.assertRaises(DeserializationError, load_tags_from_temp_file, filename)
        self.assertRaises(
            DeserializationError, load_http_response_from_temp_file, filename
        )

    def test_remove_file_if_exists(self):
        filename = write_tags_to_temp_file([])

        remove_file_if_exists(filename)
        remove_file_if_exists(filename)

        self.assertFalse(os.path.exists(filename))
