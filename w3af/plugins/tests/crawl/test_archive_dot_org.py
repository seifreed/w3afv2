"""
test_archive_dot_org.py

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

import w3af.core.controllers.output_manager as om
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.request.fuzzable_request import FuzzableRequest
from w3af.core.exceptions import RunOnce
from w3af.plugins.crawl.archive_dot_org import archive_dot_org
from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest

# Public IP address targets: deciding that they are not private sites does
# not require any DNS query
ARCHIVED_SITE = "http://8.8.8.8/"
NOT_ARCHIVED_SITE = "http://8.8.4.4/"
EMPTY_ARCHIVE_SITE = "http://1.0.0.1/"

WAYBACK = "http://web.archive.org/web"


def archive_page(*snapshot_urls):
    links = "".join(f'<a href="{url}">snapshot</a>' for url in snapshot_urls)
    return f"<html><body><div id='wm-ipp'>{links}</div></body></html>"


class TestArchiveDotOrg(PluginTest):

    target_url = ARCHIVED_SITE

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(
            f"{WAYBACK}/*/{ARCHIVED_SITE}",
            archive_page(
                f"{WAYBACK}/20110101000000/{ARCHIVED_SITE}download/",
                f"{WAYBACK}/20110101000000/{ARCHIVED_SITE}blog/#comments",
                f"{WAYBACK}/20110101000000/http://www.example.org/",
            ),
        ),
        MockResponse(
            f"{WAYBACK}/20110101000000/{ARCHIVED_SITE}download/",
            archive_page(f"{WAYBACK}/20120101000000/{ARCHIVED_SITE}community/"),
        ),
        MockResponse(f"{WAYBACK}/20110101000000/{ARCHIVED_SITE}blog/", archive_page()),
        MockResponse(
            f"{WAYBACK}/*/{ARCHIVED_SITE}download/",
            archive_page(
                f"{WAYBACK}/20110101000000/{ARCHIVED_SITE}blog/",
                f"{WAYBACK}/20150101000000/{ARCHIVED_SITE}download/",
            ),
        ),
        MockResponse(
            f"{WAYBACK}/20150101000000/{ARCHIVED_SITE}download/", archive_page()
        ),
        MockResponse(
            f"{WAYBACK}/20120101000000/{ARCHIVED_SITE}community/",
            archive_page(f"{WAYBACK}/20130101000000/{ARCHIVED_SITE}deleted/"),
        ),
        MockResponse(
            f"{WAYBACK}/*/{NOT_ARCHIVED_SITE}",
            "<html><body>" f"{archive_dot_org.NOT_IN_ARCHIVE}" "</body></html>",
        ),
        MockResponse(f"{WAYBACK}/*/{EMPTY_ARCHIVE_SITE}", archive_page()),
        MockResponse(ARCHIVED_SITE, "<html><body>Home</body></html>"),
        MockResponse(f"{ARCHIVED_SITE}download/", "<html><body>Download</body></html>"),
        MockResponse(f"{ARCHIVED_SITE}blog/", "<html><body>Blog</body></html>"),
        MockResponse(
            f"{ARCHIVED_SITE}community/", "<html><body>Community</body></html>"
        ),
    ]

    def create_plugin(self):
        plugin = archive_dot_org()
        plugin.set_url_opener(self.w3afcore.uri_opener)
        plugin.set_worker_pool(self.w3afcore.worker_pool)
        plugin.set_w3af_core(self.w3afcore)
        plugin.set_configuration(self.w3afcore.configuration)
        plugin.set_output(om.out)
        return plugin

    def test_found_urls(self):
        plugins = {
            "crawl": (
                PluginConfig("archive_dot_org", ("max_depth", 3, PluginConfig.INT)),
            )
        }
        self._scan(self.target_url, plugins)

        urls = {u.url_string for u in self.kb.get_all_known_urls()}
        expected = {
            ARCHIVED_SITE,
            f"{ARCHIVED_SITE}download/",
            f"{ARCHIVED_SITE}blog/",
            f"{ARCHIVED_SITE}community/",
        }
        self.assertEqual(urls, expected)

        requested = {r.uri for r in self.received_requests}
        self.assertIn(f"{ARCHIVED_SITE}deleted/", requested)

    def test_max_depth_limits_spidering(self):
        plugin = self.create_plugin()
        options = plugin.get_options()
        options["max_depth"].set_value(1)
        plugin.set_options(options)

        plugin.crawl(FuzzableRequest(URL(self.target_url)), "debugging-id")

        requested = {r.uri for r in self.received_requests}
        self.assertIn(f"{ARCHIVED_SITE}download/", requested)
        self.assertNotIn(
            URL(f"{WAYBACK}/20110101000000/{ARCHIVED_SITE}download/").url_string,
            requested,
        )

    def test_snapshots_are_analyzed_once(self):
        plugin = self.create_plugin()

        plugin.crawl(FuzzableRequest(URL(self.target_url)), "debugging-id")
        plugin.crawl(FuzzableRequest(URL(f"{ARCHIVED_SITE}download/")), "debugging-id")

        requested = [URL(r.uri) for r in self.received_requests]
        for snapshot in (
            f"{WAYBACK}/20110101000000/{ARCHIVED_SITE}blog/",
            f"{WAYBACK}/20150101000000/{ARCHIVED_SITE}download/",
        ):
            self.assertEqual(requested.count(URL(snapshot)), 1, snapshot)

        self.assertEqual(requested.count(URL(f"{ARCHIVED_SITE}download/")), 1)

    def test_empty_archive(self):
        plugin = self.create_plugin()
        plugin.crawl(FuzzableRequest(URL(EMPTY_ARCHIVE_SITE)), "debugging-id")

        self.assertTrue(plugin.output_queue.empty())

    def test_raise_on_domain_not_in_archive(self):
        plugin = self.create_plugin()
        fuzzable_request = FuzzableRequest(URL(NOT_ARCHIVED_SITE))

        self.assertRaises(RunOnce, plugin.crawl, fuzzable_request, "debugging-id")

    def test_raise_on_local_domain(self):
        fuzzable_request = FuzzableRequest(URL("http://127.0.0.1/"))
        plugin = archive_dot_org()
        plugin.set_output(om.out)

        self.assertRaises(RunOnce, plugin.crawl, fuzzable_request, "debugging-id")

    def test_long_description(self):
        self.assertIn("time machine", archive_dot_org().get_long_desc())
