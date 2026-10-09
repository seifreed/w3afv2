"""
test_html_file.py

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
import urllib.parse
from io import StringIO
from pathlib import Path
from typing import ClassVar

from lxml import etree

from w3af.core.data.db.history import HistoryItem
from w3af.core.data.dc.headers import Headers
from w3af.core.data.kb.tests.test_vuln import MockVuln
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.url.http_request import HTTPRequest
from w3af.core.data.url.http_response import HTTPResponse
from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest


def reflect_xss(mock_response, request, uri, response_headers):
    """Reflect the `text` parameter unescaped, emulating a reflected XSS."""
    response_headers["content-type"] = "text/html"
    query = urllib.parse.urlsplit(request.uri).query
    text = urllib.parse.parse_qs(query).get("text", [""])[0]
    body = f"<html><body>You searched for: {text}</body></html>"
    return 200, response_headers, body


class TestHTMLOutput(PluginTest):

    target_url = "http://mock/audit/xss/"
    OUTPUT_FILE = "output-unittest.html"

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(
            target_url,
            body=(
                "<html><body>"
                '<a href="xss_1.py?text=1">one</a>'
                '<a href="xss_2.py?text=1">two</a>'
                "</body></html>"
            ),
            method="GET",
        ),
        MockResponse(
            re.compile(r"http://mock/audit/xss/xss_1\.py.*"),
            body=reflect_xss,
            method="GET",
        ),
        MockResponse(
            re.compile(r"http://mock/audit/xss/xss_2\.py.*"),
            body=reflect_xss,
            method="GET",
        ),
    ]

    _run_configs: ClassVar[dict[str, object]] = {
        "cfg": {
            "target": target_url,
            "plugins": {
                "audit": (
                    PluginConfig(
                        "xss",
                        ("checkStored", True, PluginConfig.BOOL),
                        ("numberOfChecks", 3, PluginConfig.INT),
                    ),
                ),
                "crawl": (
                    PluginConfig(
                        "web_spider", ("only_forward", True, PluginConfig.BOOL)
                    ),
                ),
                "output": (
                    PluginConfig(
                        "html_file", ("output_file", OUTPUT_FILE, PluginConfig.STR)
                    ),
                ),
            },
        }
    }

    def test_found_xss(self):
        cfg = self._run_configs["cfg"]
        self._scan(cfg["target"], cfg["plugins"])

        xss_vulns = self.kb.get("xss", "xss")
        file_vulns = self._from_html_get_vulns()

        self.assertGreaterEqual(len(xss_vulns), 2)

        self.assertEqual(
            {v.get_url() for v in xss_vulns},
            {v.get_url() for v in file_vulns},
        )

        self._validate_xhtml()

    def _from_html_get_vulns(self):
        vuln_url_re = re.compile('<li>Vulnerable URL: <a href="(.*?)">')
        vulns = []

        with Path(self.OUTPUT_FILE).open(encoding="utf-8") as output_file:
            for line in output_file:
                mo = vuln_url_re.search(line)
                if mo:
                    url = URL(mo.group(1))
                    v = MockVuln("TestCase", None, "High", 1, "plugin")
                    v.set_url(url)
                    vulns.append(v)

        return vulns

    def _validate_xhtml(self):
        parser = etree.XMLParser()

        def generate_msg(parser):
            msg = "XHTML parsing errors:\n"
            for error in parser.error_log:
                msg += f"\n    {error.message} (line: {error.line}, column: {error.column})"
            return msg

        try:
            etree.parse(self.OUTPUT_FILE, parser)
        except etree.XMLSyntaxError:
            self.fail(generate_msg(parser))
        else:
            if hasattr(parser, "error_log"):
                self.assertFalse(len(parser.error_log), generate_msg(parser))

    def tearDown(self):
        super().tearDown()
        Path(self.OUTPUT_FILE).unlink(missing_ok=True)


class TestHTMLRendering(PluginTest):

    CONTEXT: ClassVar[dict[str, object]] = {
        "target_urls": ["http://w3af.com/", "http://w3af.com/blog"],
        "target_domain": "w3af.com",
        "enabled_plugins": {"audit": ["xss"], "crawl": ["web_spider"]},
        "findings": [
            MockVuln("SQL injection", None, "High", 1, "sqli"),
            MockVuln("XSS-2", None, "Medium", [], "xss"),
            MockVuln("XSS-3", None, "Low", [], "xss"),
            MockVuln("XSS-4", None, "Information", 4, "xss"),
        ],
        "debug_log": [
            ("Fri Mar 13 14:11:58 2015", "debug", "Log 1" * 40),
            ("Fri Mar 13 14:11:59 2015", "debug", "Log 2"),
            ("Fri Mar 13 14:11:59 2015", "error", "Log 3" * 5),
        ],
        "known_urls": [
            URL("http://w3af.com"),
            URL("http://w3af.com/blog"),
            URL("http://w3af.com/oss"),
        ],
    }

    def setUp(self):
        super().setUp()
        self.plugin = self.w3afcore.plugins.get_plugin_inst("output", "html_file")

        HistoryItem().init()

        url = URL("http://w3af.com/a/b/c.php")
        request = HTTPRequest(url, data="a=1")
        hdr = Headers([("Content-Type", "text/html")])
        res = HTTPResponse(200, "<html>", hdr, url, url)
        h1 = HistoryItem()
        h1.request = request
        res.set_id(1)
        h1.response = res
        h1.save()

        url = URL("http://w3af.com/foo.py")
        request = HTTPRequest(url, data="text=xss")
        hdr = Headers([("Content-Type", "text/html")])
        res = HTTPResponse(200, "<html>empty</html>", hdr, url, url)
        h1 = HistoryItem()
        h1.request = request
        res.set_id(4)
        h1.response = res
        h1.save()

    def test_render(self):
        output = StringIO()
        with open(self.plugin._template, encoding="utf-8") as template:
            result = self.plugin._render_html_file(template, self.CONTEXT, output)

        self.assertTrue(result)
        self.assertTrue(output.getvalue())

    def test_render_escapes_target_domain(self):
        output = StringIO()
        context = self.CONTEXT.copy()
        context["target_domain"] = "<script>alert(1)</script>"

        with open(self.plugin._template, encoding="utf-8") as template:
            self.plugin._render_html_file(template, context, output)

        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", output.getvalue())
