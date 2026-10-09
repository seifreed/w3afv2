"""
test_url_parameter.py

Copyright 2016 Andres Riancho

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
from w3af.core.data.url import opener_settings
from w3af.core.data.url.handlers.tests.local_server import LocalServer, Reply
from w3af.core.data.url.http_request import HTTPRequest


class TestURLParameterHandler(unittest.TestCase):
    def test_handler_integration(self):
        """
        Integration test with w3af's URL opener.
        """
        test_param = "test_handler_integration"

        settings = opener_settings.OpenerSettings()
        settings.set_url_parameter(test_param)
        settings.build_openers()
        opener = settings.get_custom_opener()

        routes = {
            "/abc/def.html": Reply(body="FAIL"),
            f"/abc/def.html;{test_param}": Reply(body="SUCCESS"),
        }

        for tls in (False, True):
            with LocalServer(routes, tls=tls) as server:
                request = HTTPRequest(URL(server.url("/abc/def.html")))
                response = opener.open(request)

            self.assertIn(b"SUCCESS", response.read())
