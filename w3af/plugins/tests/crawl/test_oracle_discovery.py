"""
test_oracle_discovery.py

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

from typing import ClassVar

from w3af.plugins.crawl.oracle_discovery import oracle_discovery
from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest

PPE_PAGE = (
    "<html><head><title>PPE is working</title></head>"
    "<body>PPE version 1.3.4 is working.</body></html>"
)

REPORTS_PAGE = (
    "<html><body>Reports Servlet Variables de Entorno 9.0.4.0.33</body></html>"
)


class TestOracleDiscovery(PluginTest):

    target_url = "http://mock/"

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(target_url, "index"),
        MockResponse(target_url + "portal/page", PPE_PAGE),
        MockResponse(target_url + "reports/rwservlet/showenv", REPORTS_PAGE),
    ]

    _run_config: ClassVar[dict] = {
        "target": target_url,
        "plugins": {"crawl": (PluginConfig("oracle_discovery"),)},
    }

    def test_oracle_discovery(self):
        self._scan(self._run_config["target"], self._run_config["plugins"])

        infos = self.kb.get("oracle_discovery", "oracle_discovery")
        descriptions = sorted(info.get_desc() for info in infos)

        self.assertEqual(len(infos), 2, infos)
        self.assertIn('"Ppe" version "1.3.4"', descriptions[0])
        self.assertIn('"Reports Servlet" version "9.0.4.0.33"', descriptions[1])

        urls = [url.url_string for url in self.kb.get_all_known_urls()]

        self.assertIn(self.target_url + "portal/page", urls)
        self.assertIn(self.target_url + "reports/rwservlet/showenv", urls)

    def test_long_desc(self):
        self.assertIn("Oracle", oracle_discovery().get_long_desc())


class TestOracleDiscoveryNotFound(PluginTest):

    target_url = "http://mock/"

    MOCK_RESPONSES: ClassVar[list] = [MockResponse(target_url, "index")]

    def test_no_oracle_pages(self):
        self._scan(self.target_url, {"crawl": (PluginConfig("oracle_discovery"),)})

        self.assertEqual(self.kb.get("oracle_discovery", "oracle_discovery"), [])
