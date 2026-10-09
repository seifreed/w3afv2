"""
test_form_autocomplete.py

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

import w3af.core.data.kb.knowledge_base as kb
from w3af.core.data.dc.headers import Headers
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.request.fuzzable_request import FuzzableRequest
from w3af.core.data.url.http_response import HTTPResponse
from w3af.core.filesystem import create_temp_dir
from w3af.plugins.grep.form_autocomplete import form_autocomplete

FORM_DEFAULT = '<form action="/login"><input type="password" name="p"></form>'
FORM_ON = (
    '<form action="/login" autocomplete="on">' '<input type="password" name="p"></form>'
)
FORM_OFF = (
    '<form action="/login" autocomplete="off">'
    '<input type="password" name="p"></form>'
)
FORM_FIELD_OFF = (
    '<form action="/login">'
    '<input type="password" name="p" autocomplete="off"></form>'
)
FORM_NO_PASSWORD = '<form action="/login"><input type="text" name="u"></form>'


class TestFormAutocomplete(unittest.TestCase):

    def setUp(self):
        create_temp_dir()
        kb.kb.cleanup()
        self.plugin = form_autocomplete()

    def tearDown(self):
        kb.kb.cleanup()

    def _grep(self, body, url, content_type="text/html"):
        headers = Headers([("content-type", content_type)])
        response = HTTPResponse(200, body, headers, url, url, _id=1)
        self.plugin.grep(FuzzableRequest(url, method="GET"), response)

    def test_found_vuln(self):
        base = "http://www.w3af.com/"
        # Each form targets a distinct action so the plugin reports one
        # grouped finding per vulnerable URL (grouping key is the form action).
        filenames = [
            "form-default.html",
            "form-on.html",
            "form-on-field-on.html",
            "form-two-fields.html",
        ]
        for filename in filenames:
            body = (
                f'<form action="/{filename}">' '<input type="password" name="p"></form>'
            )
            self._grep(body, URL(base + filename))

        vulns = kb.kb.get("form_autocomplete", "form_autocomplete")
        found = sorted(v.get_url().get_file_name() for v in vulns)
        self.assertEqual(sorted(filenames), found)

    def test_autocomplete_off_form(self):
        self._grep(FORM_OFF, URL("http://www.w3af.com/off.html"))
        self.assertEqual(0, len(kb.kb.get("form_autocomplete", "form_autocomplete")))

    def test_autocomplete_off_field(self):
        self._grep(FORM_FIELD_OFF, URL("http://www.w3af.com/field-off.html"))
        self.assertEqual(0, len(kb.kb.get("form_autocomplete", "form_autocomplete")))

    def test_no_password_field(self):
        self._grep(FORM_NO_PASSWORD, URL("http://www.w3af.com/no-pass.html"))
        self.assertEqual(0, len(kb.kb.get("form_autocomplete", "form_autocomplete")))

    def test_not_text(self):
        self._grep(FORM_DEFAULT, URL("http://www.w3af.com/x.png"), "image/png")
        self.assertEqual(0, len(kb.kb.get("form_autocomplete", "form_autocomplete")))


class TestFormAutocompleteRaw(unittest.TestCase):
    def setUp(self):
        create_temp_dir()
        kb.kb.cleanup()
        self.plugin = form_autocomplete()

    def tearDown(self):
        kb.kb.cleanup()

    def test_form_autocomplete_group_info_set(self):
        body = '<form action="/login"><input type="password" name="p"></form>'
        url_1 = URL("http://www.w3af.com/1")
        url_2 = URL("http://www.w3af.com/2")
        headers = Headers([("content-type", "text/html")])
        request = FuzzableRequest(url_1, method="GET")
        resp_1 = HTTPResponse(200, body, headers, url_1, url_1, _id=1)
        resp_2 = HTTPResponse(200, body, headers, url_2, url_2, _id=1)

        self.plugin.grep(request, resp_1)
        self.plugin.grep(request, resp_2)
        self.plugin.end()

        expected_desc = (
            "The application contains 2 different URLs with a"
            " <form> element which has auto-complete enabled"
            " for password fields. The first two vulnerable"
            " URLs are:\n"
            " - http://www.w3af.com/1\n"
            " - http://www.w3af.com/2\n"
        )

        # pylint: disable=E1103
        (info_set,) = kb.kb.get("form_autocomplete", "form_autocomplete")
        self.assertEqual(set(info_set.get_urls()), {url_1, url_2})
        self.assertEqual(info_set.get_desc(), expected_desc)
        # pylint: enable=E1103
