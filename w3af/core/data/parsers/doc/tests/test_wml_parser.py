"""
test_wml_parser.py

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

from w3af.core.data.dc.headers import Headers
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.parsers.doc.wml_parser import WMLParser
from w3af.core.data.url.http_response import HTTPResponse


class TestWMLParser(unittest.TestCase):

    def setUp(self):
        self.url = URL("http://www.w3af.com/")

    def test_parser_simple_form(self):
        form = """<go method="post" href="post.php">
                    <postfield name="clave" value="$(clave)"/>
                    <postfield name="cuenta" value="$(cuenta)"/>
                    <postfield name="tipdat" value="D"/>
                </go>"""

        response = HTTPResponse(200, form, Headers(), self.url, self.url)

        w = WMLParser(response)
        w.parse()
        forms = w.get_forms()

        self.assertEqual(len(forms), 1)
        form = forms[0]

        self.assertEqual(form.get_action().url_string, "http://www.w3af.com/post.php")

        self.assertIn("clave", form)
        self.assertIn("cuenta", form)
        self.assertIn("tipdat", form)

    def test_parser_simple_link(self):
        response = HTTPResponse(
            200, '<a href="/index.aspx">ASP.NET</a>', Headers(), self.url, self.url
        )
        w = WMLParser(response)
        w.parse()
        re, parsed = w.get_references()

        # TODO: Shouldn't this be the other way around?!
        self.assertEqual(len(parsed), 0)
        self.assertEqual("http://www.w3af.com/index.aspx", re[0].url_string)

    def parse(self, body):
        response = HTTPResponse(200, body, Headers(), self.url, self.url)
        parser = WMLParser(response)
        parser.parse()
        return parser

    def test_can_parse(self):
        wml = Headers([("content-type", "text/vnd.wap.wml")])
        document = (
            '<?xml version="1.0"?>'
            '<!DOCTYPE wml PUBLIC "-//WAPFORUM//DTD WML 1.1//EN">'
        )

        def response(body, headers):
            return HTTPResponse(200, body, headers, self.url, self.url)

        self.assertTrue(WMLParser.can_parse(response(document, wml)))
        self.assertFalse(WMLParser.can_parse(response("<wml></wml>", wml)))
        self.assertFalse(WMLParser.can_parse(response(document, Headers())))

    def test_go_without_href_posts_to_the_current_url(self):
        forms = self.parse('<go><postfield name="a" value="1"/></go>').get_forms()

        self.assertEqual(forms[0].get_action(), self.url)
        self.assertEqual(forms[0].get_method(), "GET")

    def test_go_with_invalid_href_posts_to_the_current_url(self):
        body = '<go href="javascript:"><setvar name="a"/></go>'
        forms = self.parse(body).get_forms()

        self.assertEqual(forms[0].get_action(), self.url)
        self.assertIn("a", forms[0])

    def test_fields_outside_go_are_ignored(self):
        parser = self.parse(
            '<input name="lost"/><select name="s"><option value="1"/></select>'
        )

        self.assertEqual(parser.get_forms(), [])

    def test_select_options(self):
        body = (
            '<go href="post.php">'
            '<select name="color"><option value="red"/><option value="blue"/>'
            "</select>"
            '<select><option value="ignored"/></select>'
            "</go>"
        )

        form = self.parse(body).get_forms()[0]

        self.assertEqual(dict(form), {"color": ["red", "blue"]})
