"""
test_sed.py

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

from w3af.core.controllers.exceptions import BaseFrameworkException
from w3af.core.data.dc.headers import Headers
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.url.http_request import HTTPRequest
from w3af.core.data.url.http_response import HTTPResponse
from w3af.core.filesystem import create_temp_dir
from w3af.plugins import mangle
from w3af.plugins.mangle.sed import sed


class TestSed(unittest.TestCase):

    def setUp(self):
        create_temp_dir()
        self.plugin = sed()
        self.url = URL("http://www.w3af.com/")
        self.request = HTTPRequest(self.url)

    def tearDown(self):
        self.plugin.end()

    def test_blank_body(self):
        body = ""
        headers = Headers([("content-type", "text/html")])
        response = HTTPResponse(200, body, headers, self.url, self.url, _id=1)

        option_list = self.plugin.get_options()
        option_list["expressions"].set_value("qh/User/NotLuser/")
        self.plugin.set_options(option_list)

        mod_request = self.plugin.mangle_request(self.request)
        mod_response = self.plugin.mangle_response(response)

        self.assertEqual(mod_request.get_headers(), self.request.get_headers())
        self.assertEqual(mod_response.get_headers(), response.get_headers())

        self.assertEqual(mod_request.get_uri(), self.request.get_uri())
        self.assertEqual(mod_response.get_uri(), response.get_uri())

        self.assertEqual(mod_response.get_body(), response.get_body())

    def test_response_body(self):
        body = "hello user!"
        headers = Headers([("content-type", "text/html")])
        response = HTTPResponse(200, body, headers, self.url, self.url, _id=1)

        option_list = self.plugin.get_options()
        option_list["expressions"].set_value("sb/user/notluser/")
        self.plugin.set_options(option_list)

        mod_request = self.plugin.mangle_request(self.request)
        mod_response = self.plugin.mangle_response(response)

        self.assertEqual(mod_request.get_headers(), self.request.get_headers())
        self.assertEqual(mod_response.get_headers(), response.get_headers())

        self.assertEqual(mod_request.get_uri(), self.request.get_uri())
        self.assertEqual(mod_response.get_uri(), response.get_uri())

        self.assertEqual(mod_response.get_body(), "hello notluser!")

    def test_request_headers(self):
        headers = Headers([("content-type", "text/html")])
        request = HTTPRequest(self.url, headers=headers)

        option_list = self.plugin.get_options()
        option_list["expressions"].set_value("qh/html/xml/")
        self.plugin.set_options(option_list)

        mod_request = self.plugin.mangle_request(request)

        value, _ = mod_request.get_headers().iget("content-type")
        self.assertEqual(value, "text/xml")

        self.assertIs(mod_request, request)

    def _configure(self, expressions, fix_content_len=True):
        option_list = self.plugin.get_options()
        option_list["expressions"].set_value(expressions)
        option_list["fix_content_len"].set_value(fix_content_len)
        self.plugin.set_options(option_list)

    def test_request_body(self):
        request = HTTPRequest(self.url, data="user=admin&pass=secret")
        self._configure("qb/admin/root/")

        mod_request = self.plugin.mangle_request(request)

        self.assertEqual(mod_request.get_data(), b"user=root&pass=secret")

    def test_request_without_body_is_untouched(self):
        self._configure("qb/admin/root/")

        mod_request = self.plugin.mangle_request(self.request)

        self.assertIsNone(mod_request.get_data())

    def test_response_headers(self):
        headers = Headers([("content-type", "text/html"), ("Server", "Apache")])
        response = HTTPResponse(200, "abc", headers, self.url, self.url, _id=1)
        self._configure("sh/Apache/nginx/")

        mod_response = self.plugin.mangle_response(response)

        value, _ = mod_response.get_headers().iget("server")
        self.assertEqual(value, "nginx")

    def test_response_content_length_is_fixed(self):
        headers = Headers([("content-type", "text/html"), ("Content-Length", "3")])
        response = HTTPResponse(200, "abc", headers, self.url, self.url, _id=1)
        self._configure("sb/abc/abcdef/")

        mod_response = self.plugin.mangle_response(response)

        value, _ = mod_response.get_headers().iget("content-length")
        self.assertEqual(value, "6")

    def test_response_content_length_not_fixed(self):
        headers = Headers([("content-type", "text/html"), ("Content-Length", "3")])
        response = HTTPResponse(200, "abc", headers, self.url, self.url, _id=1)
        self._configure("sb/abc/abcdef/", fix_content_len=False)

        mod_response = self.plugin.mangle_response(response)

        value, _ = mod_response.get_headers().iget("content-length")
        self.assertEqual(value, "3")

    def test_invalid_response_header_mangling_keeps_headers(self):
        headers = Headers([("content-type", "text/html")])
        response = HTTPResponse(200, "abc", headers, self.url, self.url, _id=1)
        self._configure("sh/:/-/", fix_content_len=False)

        mod_response = self.plugin.mangle_response(response)

        value, _ = mod_response.get_headers().iget("content-type")
        self.assertEqual(value, "text/html")

    def test_invalid_expression(self):
        option_list = self.plugin.get_options()
        option_list["expressions"].set_value("xx/foo/bar/")

        self.assertRaises(BaseFrameworkException, self.plugin.set_options, option_list)

    def test_invalid_regular_expression(self):
        option_list = self.plugin.get_options()
        option_list["expressions"].set_value("qb/(unbalanced/bar/")

        self.assertRaises(BaseFrameworkException, self.plugin.set_options, option_list)

    def test_long_desc(self):
        self.assertIn("stream editor", self.plugin.get_long_desc())


class TestManglePackage(unittest.TestCase):
    def test_long_description(self):
        self.assertIn("Mangle plugins", mangle.get_long_description())
