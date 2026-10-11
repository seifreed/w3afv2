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

from w3af.core.data.kb.config import Config
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.url import opener_settings
from w3af.core.data.url.http_request import HTTPRequest
from w3af.core.data.url.tests.helpers.certificates import server_tls_context
from w3af.core.data.url.tests.helpers.route_server import Response, Route, RouteServer
from w3af.core.data.url.url_parameter_settings import URLParameterSettings


class TestURLParameterHandler(unittest.TestCase):
    def test_settings_use_the_injected_configuration(self):
        configuration = Config()
        settings = URLParameterSettings(configuration)

        settings.set_url_parameter(' "tracking" ')

        self.assertEqual(configuration.get("url_parameter"), "tracking")

    def test_handler_integration(self):
        """
        Integration test with w3af's URL opener.
        """
        test_param = "test_handler_integration"

        settings = opener_settings.OpenerSettings()
        settings.set_url_parameter(test_param)
        settings.build_openers()
        opener = settings.get_custom_opener()

        routes: dict[str, Route] = {
            "/abc/def.html": Response(body="FAIL"),
            f"/abc/def.html;{test_param}": Response(body="SUCCESS"),
        }

        for tls in (False, True):
            with RouteServer(
                routes, tls_context=server_tls_context() if tls else None
            ) as server:
                request = HTTPRequest(URL(server.url("/abc/def.html")))
                response = opener.open(request)

            self.assertIn(b"SUCCESS", response.read())
