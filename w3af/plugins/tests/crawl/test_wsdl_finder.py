"""
test_wsdl_finder.py

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

from w3af.plugins.crawl.wsdl_finder import wsdl_finder
from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest

BASE_URL = "http://mock/w3af/crawl/wsdl_finder/"

INDEX = (
    "<html><body>"
    '<a href="web_service_server.php">service</a>'
    '<a href="web_service_server.php?action=list">list</a>'
    "</body></html>"
)

WSDL = """<?xml version="1.0"?>
<wsdl:definitions xmlns:wsdl="http://schemas.xmlsoap.org/wsdl/">
  <wsdl:operation name="hello">
    <soap:body use="literal"/>
  </wsdl:operation>
</wsdl:definitions>
"""


class TestWSDLFinder(PluginTest):

    target_url = BASE_URL

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(BASE_URL, INDEX),
        MockResponse(BASE_URL + "web_service_server.php", "Use ?wsdl"),
        MockResponse(BASE_URL + "web_service_server.php?action=list", "Nothing"),
        MockResponse(BASE_URL + "web_service_server.php?wsdl", WSDL, "text/xml"),
    ]

    _run_configs: ClassVar[dict] = {
        "cfg": {
            "target": target_url,
            "plugins": {
                "crawl": (
                    PluginConfig("wsdl_finder"),
                    PluginConfig(
                        "web_spider", ("only_forward", True, PluginConfig.BOOL)
                    ),
                ),
            },
        }
    }

    def test_wsdl_found(self):
        cfg = self._run_configs["cfg"]
        self._scan(cfg["target"], cfg["plugins"])

        infos = self.kb.get("wsdl_greper", "wsdl")

        self.assertEqual(len(infos), 1, infos)

        info = infos[0]

        self.assertIn("WSDL resource", info.get_name())
        self.assertEqual(info.get_url().url_string, BASE_URL + "web_service_server.php")

        wsdl_requests = [
            r.uri for r in self.received_requests if r.uri.lower().endswith("?wsdl")
        ]
        self.assertEqual(len(wsdl_requests), len(set(wsdl_requests)))


def test_wsdl_finder_metadata():
    plugin = wsdl_finder()

    if plugin.get_plugin_deps() != ["grep.wsdl_greper"]:
        raise AssertionError
    if "?WSDL" not in plugin.get_long_desc():
        raise AssertionError
