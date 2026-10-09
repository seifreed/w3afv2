"""
test_error_500.py

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
from w3af.plugins.grep.error_500 import error_500


class TestError500(unittest.TestCase):

    def setUp(self):
        create_temp_dir()
        kb.kb.cleanup()
        self.plugin = error_500()
        self.url = URL("http://www.w3af.com/500.py?id=1")
        self.request = FuzzableRequest(self.url)

    def tearDown(self):
        kb.kb.cleanup()

    def _grep(self, code, body="<html>error</html>", content_type="text/html"):
        headers = Headers([("content-type", content_type)])
        response = HTTPResponse(code, body, headers, self.url, self.url, _id=1)
        self.plugin.grep(self.request, response)

    def test_found_vuln(self):
        self._grep(500)
        self.plugin.end()

        vulns = kb.kb.get("error_500", "error_500")
        self.assertEqual(1, len(vulns))

        vuln = vulns[0]
        self.assertEqual(vuln.get_name(), "Unhandled error in web application")
        self.assertEqual(vuln.get_url().get_file_name(), "500.py")

    def test_ignore_404(self):
        self._grep(404)
        self.plugin.end()
        self.assertEqual(0, len(kb.kb.get("error_500", "error_500")))

    def test_ignore_200(self):
        self._grep(200)
        self.plugin.end()
        self.assertEqual(0, len(kb.kb.get("error_500", "error_500")))

    def test_ignore_non_text(self):
        self._grep(500, content_type="image/png")
        self.plugin.end()
        self.assertEqual(0, len(kb.kb.get("error_500", "error_500")))

    def test_false_positive_bad_request(self):
        self._grep(500, body="<h1>Bad Request (Invalid URL)</h1>")
        self.plugin.end()
        self.assertEqual(0, len(kb.kb.get("error_500", "error_500")))

    def test_already_identified_is_skipped(self):
        from w3af.core.data.constants import severity
        from w3af.core.data.kb.vuln import Vuln

        vuln = Vuln("SQL", "A SQL injection was found here", severity.HIGH, 1, "sqli")
        vuln.set_url(self.url)
        kb.kb.append("sqli", "sqli", vuln)

        self._grep(500)
        self.plugin.end()

        self.assertEqual(0, len(kb.kb.get("error_500", "error_500")))
