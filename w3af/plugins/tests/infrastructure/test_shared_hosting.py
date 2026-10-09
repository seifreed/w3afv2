"""
test_shared_hosting.py

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

import urllib.parse
from typing import ClassVar

from w3af.core.data.constants import severity
from w3af.plugins.infrastructure.shared_hosting import shared_hosting
from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest
from w3af.plugins.tests.search_engine_pages import (
    BING_SEARCH_URL_RE,
    bing_results_page,
)

# Labels longer than 63 characters can not be IDNA encoded, resolving them
# fails locally without sending any DNS query
UNRESOLVABLE_DOMAIN = "a" * 64 + ".com"

# The targets are public IP addresses, so the plugin decides they are public
# sites and resolves their addresses without any DNS query. Each one is
# hosted together with a different set of sites.
HOSTED_SITES_BY_IP = {
    "8.8.8.8": [
        "http://www.cybsec.com/",
        "http://www.bonsai-sec.com/en/",
        "http://w3af.org/blog/",
    ],
    "8.8.4.4": ["http://1.1.1.1/", "http://1.1.1.1:8080/"],
    "9.9.9.9": ["http://1.1.1.1/", f"http://{UNRESOLVABLE_DOMAIN}/"],
    "1.0.0.1": ["http://1.0.0.1/", "http://1.0.0.1/index.html"],
}


def bing_ip_search(mock_response, request, uri, response_headers):
    response_headers["Content-Type"] = "text/html"

    query = urllib.parse.parse_qs(urllib.parse.urlsplit(uri).query)["q"][0]
    ip_address = query.removeprefix("ip:")

    return 200, response_headers, bing_results_page(HOSTED_SITES_BY_IP[ip_address])


class TestSharedHosting(PluginTest):

    target_url = "http://8.8.8.8/"

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(BING_SEARCH_URL_RE, body=bing_ip_search),
    ]

    plugins: ClassVar[dict] = {
        "infrastructure": (
            PluginConfig("shared_hosting", ("result_limit", 10, PluginConfig.INT)),
        )
    }

    def scan_shared_hosting(self, target):
        self._scan(target, self.plugins)
        return self.kb.get("shared_hosting", "shared_hosting")

    def test_shared_hosting(self):
        vulns = self.scan_shared_hosting("http://8.8.8.8/")

        self.assertEqual(len(vulns), 1, vulns)

        vuln = vulns[0]
        self.assertEqual(vuln.get_name(), "Shared hosting")
        self.assertEqual(vuln.get_severity(), severity.MEDIUM)
        self.assertIn("same IP address (8.8.8.8)", vuln.get_desc())

        self.assertEqual(
            {url.url_string for url in vuln["also_in_hosting"]},
            {
                "http://www.cybsec.com/",
                "http://www.bonsai-sec.com/",
                "http://w3af.org/",
            },
        )
        self.assertEqual(
            sorted(self.kb.raw_read("shared_hosting", "domains")),
            ["w3af.org", "www.bonsai-sec.com", "www.cybsec.com"],
        )

    def test_two_sites_resolving_to_the_same_address(self):
        self.assertEqual(self.scan_shared_hosting("http://8.8.4.4/"), [])

    def test_two_sites_one_unresolvable(self):
        vulns = self.scan_shared_hosting("http://9.9.9.9/")

        self.assertEqual(len(vulns), 1, vulns)
        self.assertEqual(
            sorted(self.kb.raw_read("shared_hosting", "domains")),
            ["1.1.1.1", UNRESOLVABLE_DOMAIN],
        )

    def test_single_site(self):
        self.assertEqual(self.scan_shared_hosting("http://1.0.0.1/"), [])

    def test_private_site_is_not_searched(self):
        self.assertEqual(self.scan_shared_hosting("http://127.0.0.1/"), [])

        bing_queries = [r for r in self.received_requests if "bing.com" in r.uri]
        self.assertEqual(bing_queries, [])

    def test_unresolvable_domain_has_no_addresses(self):
        self.assertEqual(shared_hosting()._get_ip_addresses(UNRESOLVABLE_DOMAIN), [])

    def test_long_description(self):
        self.assertIn("result_limit", shared_hosting().get_long_desc())
