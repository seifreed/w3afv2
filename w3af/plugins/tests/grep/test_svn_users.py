"""
test_svn_users.py

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

from w3af.core.data.constants import severity
from w3af.core.data.dc.headers import Headers
from w3af.core.data.kb.knowledge_base import DBKnowledgeBase
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.request.fuzzable_request import FuzzableRequest
from w3af.core.data.url.http_response import HTTPResponse
from w3af.core.filesystem import create_temp_dir
from w3af.plugins.grep.svn_users import svn_users

SVN_SIGNATURE = "$Id: lzio.c,v 1.24 2003/03/20 16:00:56 roberto Exp $"


class TestSVNUsers(unittest.TestCase):

    def setUp(self):
        create_temp_dir()
        kb.cleanup()
        self.plugin = svn_users()
        self.url = URL("http://www.w3af.com/index.html")
        self.request = FuzzableRequest(self.url)

    def tearDown(self):
        self.plugin.end()

    def _grep(self, body, content_type="text/html"):
        headers = Headers([("content-type", content_type)])
        response = HTTPResponse(200, body, headers, self.url, self.url, _id=1)
        self.plugin.grep(self.request, response)

    def test_found_vuln(self):
        self._grep(f"<html><body>{SVN_SIGNATURE}</body></html>")

        vulns = kb.get("svn_users", "users")
        self.assertEqual(1, len(vulns))

        v = vulns[0]
        self.assertEqual(severity.LOW, v.get_severity())
        self.assertEqual("SVN user disclosure vulnerability", v.get_name())
        self.assertEqual(self.url.url_string, v.get_url().url_string)

    def test_username_collected(self):
        self._grep(f"<html><body>{SVN_SIGNATURE}</body></html>")

        info_set = kb.get("svn_users", "users")[0]
        self.assertIn("roberto", info_set.get_desc())

    def test_no_signature(self):
        self._grep("<html><body>nothing to see here</body></html>")
        self.assertEqual(0, len(kb.get("svn_users", "users")))

    def test_not_text(self):
        self._grep(f"<html>{SVN_SIGNATURE}</html>", content_type="image/png")
        self.assertEqual(0, len(kb.get("svn_users", "users")))


kb = DBKnowledgeBase()
