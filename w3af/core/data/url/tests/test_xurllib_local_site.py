"""
test_xurllib_local_site.py

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

from w3af.core.data.dc.urlencoded_form import URLEncodedForm
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.parsers.utils.form_params import FormParameters
from w3af.core.data.url.extended_urllib import ExtendedUrllib
from w3af.tests.helpers.sqli_site import INTEGER_FORM, SQL_ERROR, SQLInjectionSite


class TestXUrllibLocalSite(unittest.TestCase):
    """
    Send requests through the whole handler chain to a local web application
    """

    def setUp(self):
        self.site = SQLInjectionSite.serve_for(self)
        self.uri_opener = ExtendedUrllib()
        self.addCleanup(self.uri_opener.end)

    def post_text(self, data):
        url = URL(f"{self.site.url}{INTEGER_FORM}")
        return self.uri_opener.POST(url, data=data, cache=False)

    def test_post_string_body(self):
        response = self.post_text("text=1%27")
        self.assertIn(SQL_ERROR, response.get_body())

    def test_post_bytes_body(self):
        response = self.post_text(b"text=1%27")
        self.assertIn(SQL_ERROR, response.get_body())

    def test_post_form_body(self):
        form_params = FormParameters()
        form_params.add_field_by_attr_items([("name", "text"), ("type", "text")])
        form = URLEncodedForm(form_params)
        form["text"] = ["7"]

        response = self.post_text(form)
        self.assertIn("Results for 7", response.get_body())

    def test_cached_response_keeps_content_type(self):
        url = URL(self.site.url)
        self.uri_opener.GET(url, cache=True)
        cached = self.uri_opener.GET(url, cache=True)

        self.assertTrue(cached.is_text_or_html())
