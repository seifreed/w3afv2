"""
test_find_vhosts.py

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

import re
import unittest
from typing import ClassVar

from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.request.fuzzable_request import FuzzableRequest
from w3af.core.data.url.extended_urllib import ExtendedUrllib
from w3af.plugins.infrastructure.find_vhosts import find_vhosts
from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest
from w3af.plugins.tests.infrastructure.canned_plugin_test import closed_port_url

TARGET = "http://w3af.org/"

DEAD_LINKS = (
    "<html><body>"
    '<a href="http://10.1.2.3/">internal</a>'
    '<a href="http://10.1.2.3/other">internal again</a>'
    '<a href="http://8.8.8.8/">public</a>'
    "</body></html>"
)


def virtual_hosts(pages):
    """
    :param pages: Maps the Host header to the body of the page it serves
    :return: A MockResponse body which serves each virtual host page, or a 404
    """

    def respond(mock_response, request, uri, headers):
        headers["Content-Type"] = "text/html"
        host = request.headers["Host"]

        if host == "admin":
            raise ConnectionResetError("The admin virtual host is broken")

        if host in pages and request.path == "/":
            return 200, headers, pages[host]

        return 404, headers, "Not found"

    return respond


class FindVhostsTest(PluginTest):

    target_url = TARGET

    plugins: ClassVar[dict] = {"infrastructure": (PluginConfig("find_vhosts"),)}

    def scan_findings(self):
        self._scan(self.target_url, self.plugins)
        return self.kb.get("find_vhosts", "find_vhosts")


class TestFindVhosts(FindVhostsTest):

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(
            re.compile(".*"),
            virtual_hosts(
                {
                    "w3af.org": "<html><body>Welcome to w3af.org</body></html>",
                    "intranet": "Intranet secrets are here: 0123456789 " * 4,
                }
            ),
        )
    ]

    def test_find_vhosts(self):
        findings = self.scan_findings()

        self.assertEqual(len(findings), 1, findings)

        vuln = findings[0]
        self.assertEqual("Virtual host identified", vuln.get_name())
        self.assertIn('the virtual host name is: "intranet"', vuln.get_desc())


class TestFindVhostsInHTML(FindVhostsTest):

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(re.compile(".*"), virtual_hosts({"w3af.org": DEAD_LINKS}))
    ]

    def test_find_vhost_dead_link(self):
        findings = self.scan_findings()

        self.assertEqual(len(findings), 1, findings)
        self.assertEqual(findings[0].get_name(), "Internal hostname in HTML link")
        self.assertIn('"10.1.2.3"', findings[0].get_desc())


class TestFindVhostsUnparseableDocument(FindVhostsTest):

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(TARGET, b"\x89PNG\r\n\x1a\n", content_type="image/png")
    ]

    def test_no_dead_links_in_images(self):
        self.assertEqual(self.scan_findings(), [])


class TestFindVhostsUnits(unittest.TestCase):
    def test_non_existent_vhost_requests_fail(self):
        plugin = find_vhosts()
        plugin._uri_opener = ExtendedUrllib()
        self.addCleanup(plugin._uri_opener.end)

        self.assertEqual(plugin._get_non_exist(FuzzableRequest(closed_port_url())), [])

    def test_no_subdomains_for_ip_addresses(self):
        fuzzable_request = FuzzableRequest(URL("http://10.1.2.3/"))

        vhosts = list(find_vhosts()._get_common_virtual_hosts(fuzzable_request))

        self.assertEqual(vhosts, find_vhosts.COMMON_VHOSTS)

    def test_long_description(self):
        self.assertIn("Host header", find_vhosts().get_long_desc())
