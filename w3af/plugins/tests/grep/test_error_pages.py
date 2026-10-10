"""
test_error_pages.py

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

import pytest

import w3af.core.data.kb.knowledge_base as kb
from w3af.core.data.constants import severity
from w3af.core.data.dc.headers import Headers
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.request.fuzzable_request import FuzzableRequest
from w3af.core.data.url.http_response import HTTPResponse
from w3af.plugins.grep.error_pages import error_pages
from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest


@pytest.mark.ci_ready
@pytest.mark.smoke
class TestErrorPages(PluginTest):

    target_url = "http://mock/grep/error_pages/index.html"

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(
            target_url,
            body=error_pages.ERROR_PAGES[0],
            method="GET",
            status=200,
        ),
    ]

    _run_configs: ClassVar[dict] = {
        "cfg": {
            "target": target_url,
            "plugins": {"grep": (PluginConfig("error_pages"),)},
        }
    }

    def test_found_vuln(self):
        cfg = self._run_configs["cfg"]
        self._scan(cfg["target"], cfg["plugins"])

        infos = self.kb.get("error_pages", "error_page")
        self.assertEqual(1, len(infos))
        info = infos[0]

        self.assertEqual(1, len(infos), infos)
        self.assertEqual(self.target_url, str(info.get_url()))
        self.assertEqual(severity.INFORMATION, info.get_severity())
        self.assertTrue(info.get_name().startswith("Descriptive error page"))

    def setUp(self):
        super().setUp()
        kb.kb.cleanup()

    def test_found_vuln_max_reports(self):
        kb.kb.cleanup()
        plugin = error_pages()
        plugin.set_knowledge_base(kb.kb)

        body = plugin.ERROR_PAGES[5]
        headers = Headers(list({"content-type": "text/html"}.items()))

        for i in range(plugin.MAX_REPORTED_PER_MSG * 2):
            url = URL(f"http://www.w3af.com/{i}")
            request = FuzzableRequest(url, method="GET")
            response = HTTPResponse(200, body, headers, url, url, _id=1)

            plugin.grep(request, response)

        plugin.end()

        self.assertEqual(
            len(kb.kb.get("error_pages", "error_page")), plugin.MAX_REPORTED_PER_MSG + 1
        )

    def test_found_vuln_max_reports_two_different(self):
        kb.kb.cleanup()
        plugin = error_pages()
        plugin.set_knowledge_base(kb.kb)

        body = plugin.ERROR_PAGES[5]
        headers = Headers(list({"content-type": "text/html"}.items()))

        for i in range(plugin.MAX_REPORTED_PER_MSG * 2):
            url = URL(f"http://www.w3af.com/{i}")
            request = FuzzableRequest(url, method="GET")
            response = HTTPResponse(200, body, headers, url, url, _id=1)

            plugin.grep(request, response)

        # Note that here I chose a different error message
        body = plugin.ERROR_PAGES[7]
        url = URL("http://www.w3af.com/iamdifferent")
        request = FuzzableRequest(url, method="GET")
        response = HTTPResponse(200, body, headers, url, url, _id=1)

        plugin.grep(request, response)

        plugin.end()

        self.assertEqual(
            len(kb.kb.get("error_pages", "error_page")), plugin.MAX_REPORTED_PER_MSG + 2
        )
