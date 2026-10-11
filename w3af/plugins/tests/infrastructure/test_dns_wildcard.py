"""
test_dns_wildcard.py

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
from typing import ClassVar

from w3af.core.data.dc.headers import Headers
from w3af.core.data.kb.knowledge_base import DBKnowledgeBase
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.request.fuzzable_request import FuzzableRequest
from w3af.core.data.url.extended_urllib import ExtendedUrllib
from w3af.core.data.url.http_response import HTTPResponse
from w3af.plugins.infrastructure.dns_wildcard import dns_wildcard
from w3af.plugins.tests.canned_http_server import CannedReply
from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest
from w3af.plugins.tests.infrastructure.canned_plugin_test import (
    CannedServerPluginTest,
    closed_port_url,
)

HOME = "<html><body>Welcome to the localhost home page</body></html>"
OTHER = "0123456789 " * 20


class TestDNSWildcard(PluginTest):

    target_url = "http://httpretty"

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse("http://httpretty/", body="Hello world", method="GET", status=200)
    ]
    _run_configs: ClassVar[dict] = {
        "cfg": {
            "target": target_url,
            "plugins": {"infrastructure": (PluginConfig("dns_wildcard"),)},
        }
    }

    def test_wildcard(self):
        cfg = self._run_configs["cfg"]
        self._scan(cfg["target"], cfg["plugins"])

        infos = self.kb.get("dns_wildcard", "dns_wildcard")

        self.assertEqual(len(infos), 1, infos)
        self.assertEqual("DNS wildcard", infos[0].get_name())


class DNSWildcardTest(CannedServerPluginTest):
    """
    localhost always resolves to 127.0.0.1, the canned server answers the
    requests for the target domain with HOME.
    """

    plugin_class = dns_wildcard

    def respond(self, request):
        if request.headers["Host"] == "localhost":
            return CannedReply(200, {"Content-Type": "text/html"}, HOME)
        return self.respond_other_host(request)

    def respond_other_host(self, request):
        return CannedReply(200, {"Content-Type": "text/html"}, HOME)

    def discover(self, url):
        self.plugin.discover(FuzzableRequest(URL(url)), 1)
        return {i.get_name() for i in kb.get("dns_wildcard", "dns_wildcard")}


class TestSameContentEverywhere(DNSWildcardTest):
    def test_dns_wildcard(self):
        self.assertEqual(self.discover("http://localhost/"), {"DNS wildcard"})

        hosts = [request.headers["Host"] for request in self.server.requests]
        self.assertEqual(hosts, ["localhost", "foobar.localhost", "127.0.0.1"])

    def test_ip_address_targets_are_ignored(self):
        self.assertEqual(self.discover("http://127.0.0.1/"), set())
        self.assertEqual(self.server.requests, [])

    def test_subdomain_is_removed(self):
        self.discover("http://sub.localhost/")

        self.assertEqual(self.server.requests[1].headers["Host"], "localhost")


class TestOtherHostsDiffer(DNSWildcardTest):
    def respond_other_host(self, request):
        return CannedReply(200, {"Content-Type": "text/html"}, OTHER)

    def test_no_dns_wildcard_and_default_virtual_host(self):
        self.assertEqual(
            self.discover("http://localhost/"),
            {"No DNS wildcard", "Default virtual host"},
        )


class TestIPAddressFails(DNSWildcardTest):
    def respond_other_host(self, request):
        raise ConnectionResetError("Only the domain is served")

    def test_no_content_response_is_ignored(self):
        self.assertEqual(self.discover("http://localhost/"), {"No DNS wildcard"})


class TestRequestErrors(unittest.TestCase):
    """
    Without the plugin URL opener proxy, which turns failed requests into 204
    responses, the plugin itself has to handle the request errors.
    """

    def setUp(self):
        kb.cleanup()
        self.addCleanup(kb.cleanup)

        self.plugin = dns_wildcard()
        self.plugin._uri_opener = ExtendedUrllib()
        self.addCleanup(self.plugin._uri_opener.end)

        url = closed_port_url()
        url.set_domain("localhost")
        self.original_response = HTTPResponse(200, HOME, Headers(), url, url)

    def test_dns_request_fails(self):
        self.plugin._test_dns(self.original_response, URL("http://foobar.localhost/"))

        self.assertEqual(kb.get("dns_wildcard", "dns_wildcard"), [])

    def test_ip_address_request_fails(self):
        self.plugin._test_ip_address(self.original_response, "localhost")

        self.assertEqual(kb.get("dns_wildcard", "dns_wildcard"), [])

    def test_unresolvable_domain(self):
        self.plugin._test_ip_address(self.original_response, "w3af.invalid")

        self.assertEqual(kb.get("dns_wildcard", "dns_wildcard"), [])
        self.assertIn("DNS wildcard", self.plugin.get_long_desc())


kb = DBKnowledgeBase()
