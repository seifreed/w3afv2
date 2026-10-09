"""
test_login_form.py

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

import unittest

from w3af.core.data.dc.generic.form import Form
from w3af.core.data.parsers.utils.form_params import FormParameters


def form_with(*fields):
    form_params = FormParameters()
    for name, input_type in fields:
        form_params.add_field_by_attrs({"name": name, "type": input_type})
    return Form(form_params)


class TestLoginFormRequirements(unittest.TestCase):
    def test_search_form_is_not_a_login_form(self):
        form = form_with(("q", "text"))

        for call in (
            form.get_login_tokens,
            lambda: form.set_login_username("andres"),
            lambda: form.set_login_password("secret"),
        ):
            with self.assertRaisesRegex(ValueError, "^Login form is required$"):
                call()

    def test_password_only_form_has_no_username(self):
        form = form_with(("pin", "password"))

        self.assertTrue(form.is_login_form())
        self.assertEqual(form.get_login_tokens()[0], None)

        with self.assertRaisesRegex(ValueError, "with username is required"):
            form.set_login_username("andres")

        form.set_login_password("1234")
        self.assertEqual(form["pin"][0], "1234")
