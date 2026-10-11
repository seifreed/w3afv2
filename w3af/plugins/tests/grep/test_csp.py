"""
test_csp.py

Copyright 2013 Andres Riancho

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
from w3af.core.data.kb.knowledge_base import DBKnowledgeBase
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.request.fuzzable_request import FuzzableRequest
from w3af.core.data.url.http_response import HTTPResponse
from w3af.core.filesystem import create_temp_dir
from w3af.plugins.grep.csp import csp

PERMISSIVE_CSP = (
    "default-src *; script-src *; object-src *;" " def-src 'self'; sript-src 'self'"
)


class TestCSP(unittest.TestCase):

    def setUp(self):
        create_temp_dir()
        kb.cleanup()
        self.plugin = csp()
        self.url = URL("http://www.w3af.com/")
        self.request = FuzzableRequest(self.url)

    def tearDown(self):
        kb.cleanup()

    def _grep(self, csp_value, url=None):
        url = url or self.url
        headers = Headers(
            [("content-type", "text/html"), ("Content-Security-Policy", csp_value)]
        )
        response = HTTPResponse(200, "", headers, url, url, _id=1)
        self.plugin.grep(FuzzableRequest(url), response)

    def test_found_vuln(self):
        self._grep(PERMISSIVE_CSP)
        self.plugin.end()

        vulns = kb.get("csp", "csp")

        expected = {
            "Directive 'default-src' allows all sources.",
            "Directive 'script-src' allows all javascript sources.",
            (
                "Directive 'script-src' is defined but no directive"
                " 'script-nonce' is defined to protect javascript"
                " resources."
            ),
            "Directive 'object-src' allows all plugin sources.",
            "Some directives are misspelled: def-src, sript-src",
        }

        vuln_descs = {v.get_desc(with_id=False) for v in vulns}
        self.assertEqual(expected, vuln_descs)
        for v in vulns:
            self.assertEqual(v.get_name(), "CSP vulnerability")

    def test_no_csp_header(self):
        headers = Headers([("content-type", "text/html")])
        response = HTTPResponse(200, "", headers, self.url, self.url, _id=1)
        self.plugin.grep(self.request, response)
        self.plugin.end()
        self.assertEqual(len(kb.get("csp", "csp")), 0)

    def test_url_analyzed_once(self):
        self._grep(PERMISSIVE_CSP)
        self._grep(PERMISSIVE_CSP)
        self.plugin.end()
        vulns = kb.get("csp", "csp")
        vuln_urls = {v.get_url().url_string for v in vulns}
        self.assertEqual(vuln_urls, {self.url.url_string})


kb = DBKnowledgeBase()
