"""
test_url_fuzzer.py

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

from w3af.plugins.crawl.url_fuzzer import url_fuzzer
from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest

BASE_URL = "http://mock/w3af/crawl/url_fuzzer"
INDEX = "<html><body>url fuzzer index</body></html>"

FUZZED_FILES = [
    MockResponse(BASE_URL + "/index.html", INDEX),
    MockResponse(BASE_URL + "/index.html~", "backup contents ~"),
    MockResponse(BASE_URL + "/index.html.zip", "zip contents"),
    MockResponse(BASE_URL + ".tgz", "directory tarball"),
    MockResponse(BASE_URL + "/index.html.bak", "Forbidden", status=403),
    MockResponse(
        BASE_URL + "/index.html.old1",
        "",
        status=302,
        headers={"Location": BASE_URL + "/index.html"},
    ),
]

EXPECTED_FILES = {
    BASE_URL + "/index.html~",
    BASE_URL + "/index.html.zip",
    BASE_URL + ".tgz",
}


def _fuzzer_plugins(fuzz_images):
    return {
        "crawl": (
            PluginConfig("url_fuzzer", ("fuzz_images", fuzz_images, PluginConfig.BOOL)),
        )
    }


class TestURLFuzzerWithGet(PluginTest):

    target_url = BASE_URL + "/index.html"

    MOCK_RESPONSES: ClassVar[list] = FUZZED_FILES

    def test_fuzzer_found_urls(self):
        self._scan(self.target_url, _fuzzer_plugins(False))

        urls = {str(u) for u in self.kb.get_all_known_urls()}
        self.assertTrue(EXPECTED_FILES.issubset(urls), urls)
        self.assertNotIn(BASE_URL + "/index.html.bak", urls)

        reported = {str(i.get_url()) for i in self.kb.get("url_fuzzer", "files")}
        self.assertEqual(reported, EXPECTED_FILES)

        methods = {r.command for r in self.received_requests}
        self.assertNotIn("HEAD", methods)


class TestURLFuzzerWithHead(PluginTest):

    target_url = BASE_URL + "/logo.png"

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(
            BASE_URL + "/",
            "",
            method="OPTIONS",
            headers={"Allow": "OPTIONS, GET, HEAD"},
        ),
        MockResponse(BASE_URL + "/logo.png", "", "image/png", method="HEAD"),
        MockResponse(BASE_URL + "/logo.png", "PNG", "image/png"),
        MockResponse(BASE_URL + "/logo.png.bak", "image backup"),
    ]

    def test_head_is_used_and_images_fuzzed(self):
        self._scan(self.target_url, _fuzzer_plugins(True))

        head_requests = [r for r in self.received_requests if r.command == "HEAD"]
        self.assertTrue(head_requests)

        reported = {str(i.get_url()) for i in self.kb.get("url_fuzzer", "files")}
        self.assertEqual(reported, {BASE_URL + "/logo.png.bak"})


def test_url_fuzzer_metadata():
    plugin = url_fuzzer()

    if plugin.get_plugin_deps() != ["infrastructure.allowed_methods"]:
        raise AssertionError
    if "fuzz_images" not in plugin.get_long_desc():
        raise AssertionError
