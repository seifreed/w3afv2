"""
test_file_templates.py

Copyright 2006 Andres Riancho

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

from w3af.core.data.constants.file_templates.file_templates import (
    get_file_from_template,
    get_template_with_payload,
)


class TestFileTemplates(unittest.TestCase):
    def test_get_file_from_template_true(self):
        success, file_content, file_name = get_file_from_template("gif")

        self.assertTrue(success)
        self.assertIn("GIF", file_content)
        self.assertTrue(file_name.endswith(".gif"), file_name)

    def test_get_file_from_template_false(self):
        success, _file_content, file_name = get_file_from_template("swf")

        self.assertFalse(success)
        self.assertTrue(file_name.endswith(".swf"), file_name)

    def test_get_template_with_payload_replaces_marker(self):
        success, file_content, file_name = get_template_with_payload("gif", "PAYLOAD")

        self.assertTrue(success)
        self.assertTrue(file_content.startswith("GIF"))
        self.assertIn("PAYLOAD", file_content)
        self.assertNotIn("A" * 239, file_content)
        self.assertTrue(file_name.endswith(".gif"), file_name)

    def test_get_template_with_payload_accepts_bytes(self):
        _, file_content, _ = get_template_with_payload("gif", b"BYTES")

        self.assertIn("BYTES", file_content)
