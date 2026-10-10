"""
test_xurllib_proxy.py

Copyright 2011 Andres Riancho

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

import pytest

import w3af.core.controllers.output_manager as om
from w3af.core.controllers.daemons.proxy import Proxy, ProxyHandler
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.url.extended_urllib import ExtendedUrllib
from w3af.core.data.url.opener_settings import OpenerSettings
from w3af.core.data.url.tests.helpers.raw_handlers import closed_port
from w3af.core.data.url.tests.helpers.route_server import Response, RouteServer, echo

INDEX = "<title>local test application</title>"


@pytest.mark.smoke
class TestExtendedUrllibProxy(unittest.TestCase):

    def setUp(self):
        self.uri_opener = ExtendedUrllib()
        self.addCleanup(self.uri_opener.end)

        routes = {"/": Response(200, INDEX), "/echo": echo}
        self.server = RouteServer.serve_for(self, routes)
        self.ssl_server = RouteServer.serve_for(self, routes, use_tls=True)

        # Start the proxy daemon
        proxy_opener = ExtendedUrllib()
        self.addCleanup(proxy_opener.end)
        self._proxy = Proxy("127.0.0.1", 0, proxy_opener, om.out, ProxyHandler)
        self._proxy.start()
        self._proxy.wait_for_start()
        self.addCleanup(self._proxy.stop)

        # Configure the proxy
        settings = OpenerSettings()
        self.addCleanup(settings.set_default_values)
        options = settings.get_options()
        options["proxy_address"].set_value("127.0.0.1")
        options["proxy_port"].set_value(self._proxy.get_port())

        settings.set_options(options)
        self.uri_opener.settings = settings

    def test_http_port_specification_via_proxy(self):
        self.assertEqual(self._proxy.total_handled_requests, 0)

        http_response = self.uri_opener.GET(URL(self.server.url()), cache=False)

        self.assertIn(INDEX, http_response.body)
        self.assertEqual(self._proxy.total_handled_requests, 1)
        self.assertEqual(len(self.server.requests), 1)

    def test_https_via_proxy(self):
        self.assertEqual(self._proxy.total_handled_requests, 0)

        http_response = self.uri_opener.GET(URL(self.ssl_server.url()), cache=False)

        self.assertIn(INDEX, http_response.body)
        self.assertEqual(self._proxy.total_handled_requests, 1)
        self.assertEqual(len(self.ssl_server.requests), 1)

    def test_offline_port_via_proxy(self):
        url = URL(f"http://127.0.0.1:{closed_port()}/")
        http_response = self.uri_opener.GET(url, cache=False)

        self.assertEqual(http_response.get_code(), 500)
        self.assertIn("Connection refused", http_response.body)

    def test_POST_via_proxy(self):
        url = URL(self.server.url("/echo"))
        http_response = self.uri_opener.POST(url, data="text=123456abc", cache=False)

        self.assertIn("text=123456abc", http_response.body)
        self.assertEqual(self.server.requests[-1].method, "POST")
