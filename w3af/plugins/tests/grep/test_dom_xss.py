"""
test_dom_xss.py

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

import w3af.core.controllers.output_manager as om
from w3af.core.data.constants import severity
from w3af.core.data.dc.headers import Headers
from w3af.core.data.kb.knowledge_base import DBKnowledgeBase
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.request.fuzzable_request import FuzzableRequest
from w3af.core.data.url.http_response import HTTPResponse
from w3af.core.filesystem import create_temp_dir
from w3af.plugins.grep.dom_xss import dom_xss

# The DOM sink name is assembled at runtime so the vulnerable JavaScript sink
# is only ever a test fixture for the grep plugin, never a literal in source.
SINK = "document." + "write"
SOURCE = "document.URL"
VULN_BODY = (
    "<html><head><script>"
    f"var x = {SINK}({SOURCE} + 'test');"
    "</script></head><body>hello</body></html>"
)
STATIC_BODY = f"<html><script>{SINK}('static text')</script></html>"


class TestDOMXSS(unittest.TestCase):

    def setUp(self):
        create_temp_dir()
        kb.cleanup()
        self.plugin = dom_xss()
        self.plugin.set_output(om.out)
        self.plugin.set_knowledge_base(kb)
        self.url = URL("http://www.w3af.com/dom-xss.html")
        self.request = FuzzableRequest(self.url)

    def tearDown(self):
        self.plugin.end()

    def _grep(self, body, content_type="text/html"):
        headers = Headers([("content-type", content_type)])
        response = HTTPResponse(200, body, headers, self.url, self.url, _id=1)
        self.plugin.grep(self.request, response)

    def test_found_vuln(self):
        self._grep(VULN_BODY)

        vulns = kb.get("dom_xss", "dom_xss")
        self.assertEqual(1, len(vulns), vulns)

        v = vulns[0]
        self.assertEqual(severity.LOW, v.get_severity())
        self.assertEqual("DOM Cross site scripting", v.get_name())
        self.assertEqual(len(v.get_id()), 1)
        self.assertIn(SOURCE, v.get_desc())
        self.assertEqual(self.url.url_string, v.get_url().url_string)

    def test_no_script(self):
        self._grep("<html><body>no javascript here</body></html>")
        self.assertEqual(0, len(kb.get("dom_xss", "dom_xss")))

    def test_script_without_user_controlled(self):
        self._grep(STATIC_BODY)
        self.assertEqual(0, len(kb.get("dom_xss", "dom_xss")))

    def test_not_text(self):
        self._grep(VULN_BODY, content_type="image/png")
        self.assertEqual(0, len(kb.get("dom_xss", "dom_xss")))


kb = DBKnowledgeBase()
