"""
test_rosetta_flash.py

Copyright 2015 Andres Riancho

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
from typing import ClassVar

from w3af.core.data.parsers.doc.url import URL
from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest

CONFIG = {
    "audit": (PluginConfig("rosetta_flash"),),
}


class TestRosettaFlash(PluginTest):

    target_url = "http://mock/jsonp?callback="

    class JSONPMockResponse(MockResponse):
        def get_response(self, http_request, uri, response_headers):
            uri = URL(uri)

            try:
                callback = uri.get_querystring()["callback"][0]
            except KeyError:
                callback = "default"

            body = f"{callback}({{}})"
            response_headers["Content-Type"] = "application/javascript"

            return self.status, response_headers, body

    MOCK_RESPONSES: ClassVar[list] = [
        JSONPMockResponse(
            re.compile(".*"),
            body=None,
            method="GET",
            status=200,
            content_type="application/javascript",
        )
    ]

    def test_found_rosetta_flash(self):
        self._scan(self.target_url, CONFIG)
        vulns = self.kb.get("rosetta_flash", "rosetta_flash")

        self.assertEqual(1, len(vulns), vulns)

        # Now some tests around specific details of the found vuln
        vuln = vulns[0]

        self.assertEqual("callback", vuln.get_token_name())
        self.assertEqual("Rosetta Flash", vuln.get_name())
        self.assertEqual(
            URL(self.target_url).uri2url().url_string, vuln.get_url().url_string
        )


class TestRosettaFlashFixed(PluginTest):

    target_url = "http://mock/jsonp?callback="

    class JSONPMockResponse(MockResponse):
        def get_response(self, http_request, uri, response_headers):
            uri = URL(uri)

            try:
                callback = uri.get_querystring()["callback"][0]
            except KeyError:
                callback = "default"

            #
            # Here is the fix! Note the /**/
            #
            body = f"/**/{callback}({{}})"
            response_headers["Content-Type"] = "application/javascript"

            return self.status, response_headers, body

    MOCK_RESPONSES: ClassVar[list] = [
        JSONPMockResponse(
            re.compile(".*"),
            body=None,
            method="GET",
            status=200,
            content_type="application/javascript",
        )
    ]

    def test_not_found_rosetta_flash(self):
        self._scan(self.target_url, CONFIG)
        vulns = self.kb.get("rosetta_flash", "rosetta_flash")

        self.assertEqual(0, len(vulns), vulns)


def html_callback(mock_response, request, uri, response_headers):
    """Reflect the callback at the start of an HTML page."""
    callback = URL(uri).get_querystring().get("callback", ["default"])[0]
    response_headers["Content-Type"] = "text/html"
    return 200, response_headers, f"{callback}({{}})"


def untyped_callback(mock_response, request, uri, response_headers):
    """Reflect the callback without telling the content type."""
    callback = URL(uri).get_querystring().get("callback", ["default"])[0]
    return 200, response_headers, f"{callback}({{}})"


class TestRosettaFlashOnlyInScriptResponses(PluginTest):

    target_url = "http://mock/jsonp?callback="

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(re.compile(r"http://mock/jsonp\?.*"), html_callback),
        MockResponse(re.compile(r"http://mock/untyped\?.*"), untyped_callback),
    ]

    def test_html_response_is_not_audited(self):
        self._scan(self.target_url, CONFIG)

        self.assertEqual([], self.kb.get("rosetta_flash", "rosetta_flash"))
        self.assertFalse(any("CWSA7000" in r.uri for r in self.received_requests))

    def test_response_without_content_type_is_not_audited(self):
        self._scan("http://mock/untyped?callback=", CONFIG)

        self.assertEqual([], self.kb.get("rosetta_flash", "rosetta_flash"))
        self.assertFalse(any("CWSA7000" in r.uri for r in self.received_requests))
