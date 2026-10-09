"""
test_form_fields.py

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

import copy
import unittest

from w3af.core.data.parsers.utils.form_fields import (
    CheckboxFormField,
    FileFormField,
    GenericFormField,
    RadioFormField,
    SelectFormField,
    get_value_by_key,
)


class TestGenericFormField(unittest.TestCase):

    def test_repr_and_str(self):
        field = GenericFormField("text", "user", "admin")

        self.assertEqual(
            repr(field), '<Text form field (name: "user", value: "admin")>'
        )
        self.assertEqual(str(field), "admin")

    def test_equality(self):
        field = GenericFormField("text", "user", "admin")

        self.assertEqual(field, "admin")
        self.assertEqual(field, GenericFormField("text", "user", "admin"))
        self.assertNotEqual(field, GenericFormField("password", "user", "admin"))
        self.assertNotEqual(field, 42)

    def test_copy_keeps_all_slots(self):
        field = GenericFormField("text", "user", "admin", autocomplete=True)

        field_copy = copy.deepcopy(field)

        self.assertEqual(field_copy, field)
        self.assertTrue(field_copy.autocomplete)

    def test_file_field(self):
        field = FileFormField("upload", file_name="cat.png")

        self.assertEqual(field.input_type, "file")
        self.assertEqual(field.file_name, "cat.png")
        self.assertIsNone(field.value)


class TestChooseFormFields(unittest.TestCase):

    def test_first_value_is_selected(self):
        field = SelectFormField("car", ["volvo", "saab"])

        self.assertEqual(field.value, "volvo")
        self.assertEqual(field.input_type, "select")
        self.assertIsNone(RadioFormField("sex", []).value)

    def test_equality(self):
        field = CheckboxFormField("vehicle", ["bike", "car"])

        self.assertEqual(field, "bike")
        self.assertEqual(field, CheckboxFormField("vehicle", ["bike", "car"]))
        self.assertNotEqual(field, CheckboxFormField("vehicle", ["bike"]))
        self.assertNotEqual(field, RadioFormField("vehicle", ["bike", "car"]))
        self.assertNotEqual(field, GenericFormField("checkbox", "vehicle", "bike"))


class TestGetValueByKey(unittest.TestCase):

    def test_first_matching_key_wins(self):
        attrs = {"ID": "the-id", "name": "the-name"}

        self.assertEqual(get_value_by_key(attrs, "name", "id"), "the-name")
        self.assertEqual(get_value_by_key(attrs, "id"), "the-id")
        self.assertIsNone(get_value_by_key(attrs, "value"))
