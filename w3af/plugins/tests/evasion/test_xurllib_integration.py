"""
test_xurllib_integration.py

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

from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.url.extended_urllib import ExtendedUrllib
from w3af.core.filesystem import create_temp_dir
from w3af.plugins.evasion.self_reference import self_reference
from w3af.plugins.tests.canned_http_server import CannedHTTPServer, CannedReply


class TestXurllibIntegration(unittest.TestCase):

    def setUp(self):
        create_temp_dir()

        self.server = CannedHTTPServer(
            lambda request: CannedReply(200, {"Content-Type": "text/html"}, "ok")
        )
        self.server.start()
        self.addCleanup(self.server.stop)

    def test_send_mangled(self):
        xurllib = ExtendedUrllib()
        self.addCleanup(xurllib.end)
        xurllib.set_evasion_plugins([self_reference()])

        base = f"http://127.0.0.1:{self.server.port}"
        http_response = xurllib.GET(URL(f"{base}/a/b.html"))

        # The evasion is applied to the request sent on the wire, while the
        # response keeps the URL the caller asked for
        self.assertEqual(
            [request.uri for request in self.server.requests],
            [f"{base}/./a/./b.html"],
        )
        self.assertEqual(http_response.get_url().url_string, f"{base}/a/b.html")
