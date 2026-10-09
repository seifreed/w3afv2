"""
test_fingerprint_os.py

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
from typing import ClassVar

from w3af.plugins.infrastructure.fingerprint_os import fingerprint_os
from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest

INDEX = (
    "<html><body>"
    '<a href="/w3af/index.html">index</a><a href="/w3af/about.html">about</a>'
    "</body></html>"
)
PAGES = {
    "/": INDEX,
    "/w3af/index.html": "<html><body>The w3af index page</body></html>",
    "/w3af/about.html": "<html><body>About w3af: a web scanner</body></html>",
}


def site(path_separators):
    """
    :param path_separators: The path separators the web server accepts
    :return: A MockResponse body serving PAGES
    """

    def respond(mock_response, request, uri, headers):
        headers["Content-Type"] = "text/html"
        path = request.path

        for separator in path_separators:
            path = path.replace(separator, "/")

        if path in PAGES:
            return 200, headers, PAGES[path]

        return 404, headers, "Not found"

    return respond


class FingerprintOSTest(PluginTest):

    target_url = "http://target/"

    plugins: ClassVar[dict] = {
        "infrastructure": (PluginConfig("fingerprint_os"),),
        "crawl": (PluginConfig("web_spider"),),
    }

    def scan_os(self):
        self._scan(self.target_url, self.plugins)

        infos = self.kb.get("fingerprint_os", "operating_system")
        self.assertEqual(len(infos), 1, infos)
        self.assertEqual(infos[0].get_name(), "Operating system")

        return self.kb.raw_read("fingerprint_os", "operating_system_str")


class TestUnix(FingerprintOSTest):

    MOCK_RESPONSES: ClassVar[list] = [MockResponse(re.compile(".*"), site(()))]

    def test_unix(self):
        self.assertEqual(self.scan_os(), "unix")


class TestWindows(FingerprintOSTest):

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(re.compile(".*"), site(("%5C", "%5c", "\\")))
    ]

    def test_windows(self):
        self.assertEqual(self.scan_os(), "windows")

        backslash_requests = [
            r for r in self.received_requests if "/w3af%5Cindex.html" in r.uri
        ]
        self.assertEqual(len(backslash_requests), 1, self.received_requests)

    def test_long_description(self):
        self.assertIn("Operating System", fingerprint_os().get_long_desc())
