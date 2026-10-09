"""
test_content_negotiation.py

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

from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.request.fuzzable_request import FuzzableRequest
from w3af.plugins.crawl.content_negotiation import content_negotiation
from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest

BACKUP_FILES = ("backup.php", "backup.zip", "backup.gz", "backup.tar")

ALTERNATES = ", ".join(
    f'{{"{name}" 1 {{type application/octet-stream}} {{length 0}}}}'
    for name in BACKUP_FILES
)

TARGET_URL = "http://mock/"

DISABLED_LINKS = ("one.php", "two.php", "three.php", "four.php")

RUN_PLUGINS = {
    "crawl": (
        PluginConfig("content_negotiation"),
        PluginConfig("web_spider", ("only_forward", True, PluginConfig.BOOL)),
    )
}


class TestContentNegotiation(PluginTest):

    target_url = TARGET_URL

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(target_url, '<html><a href="backup.php">backup</a></html>'),
        MockResponse(
            target_url + "backup",
            "Not acceptable",
            status=406,
            headers={"Alternates": ALTERNATES},
        ),
        *(MockResponse(TARGET_URL + name, name) for name in BACKUP_FILES),
    ]

    def test_content_negotiation_find_urls(self):
        self._scan(self.target_url, RUN_PLUGINS)

        infos = self.kb.get("content_negotiation", "content_negotiation")
        self.assertEqual(len(infos), 1, infos)
        info = infos[0]
        self.assertEqual(info.get_name(), "HTTP Content Negotiation enabled")

        urls = self.kb.get_all_known_urls()
        expected_fnames = {"backup.zip", "backup.php", "backup.gz", "backup.tar", ""}
        self.assertEqual(expected_fnames, {u.get_file_name() for u in urls})

        requested_paths = {request.path for request in self.received_requests}
        self.assertIn("/admin", requested_paths)


class TestContentNegotiationDisabled(PluginTest):

    target_url = TARGET_URL

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(
            target_url,
            "".join(f'<a href="{link}">{link}</a>' for link in DISABLED_LINKS),
        ),
        *(MockResponse(TARGET_URL + link, link) for link in DISABLED_LINKS),
    ]

    def test_content_negotiation_disabled(self):
        self._scan(self.target_url, RUN_PLUGINS)

        infos = self.kb.get("content_negotiation", "content_negotiation")
        self.assertEqual(infos, [])

    def test_stops_negotiating_after_three_failed_tries(self):
        plugin = content_negotiation()
        plugin.set_url_opener(self.w3afcore.uri_opener)

        for path in ("", *DISABLED_LINKS):
            plugin.crawl(FuzzableRequest(URL(TARGET_URL + path)), None)

        negotiation_requests = [
            request
            for request in self.received_requests
            if request.headers["Accept"] == "w3af/bar"
        ]
        self.assertEqual(
            [request.path for request in negotiation_requests],
            ["/one", "/two", "/three"],
        )
        self.assertTrue(plugin._to_bruteforce.empty())


class TestFindNewResources(PluginTest):
    def test_directory_url_has_no_resources_to_find(self):
        plugin = content_negotiation()

        plugin._find_new_resources(FuzzableRequest(URL("http://mock/dir/")))

        self.assertTrue(plugin.output_queue.empty())

    def test_long_description(self):
        self.assertIn("content negotiation", content_negotiation().get_long_desc())
