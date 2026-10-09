"""
test_sitemap_xml.py

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
from w3af.plugins.crawl.sitemap_xml import sitemap_xml
from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest

TARGET_URL = "http://mock/"
SITEMAP_URL = TARGET_URL + "sitemap.xml"

SITEMAP = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>http://mock/hidden/</loc></url>
  <url><loc></loc></url>
  <url><loc>http://[::1</loc></url>
</urlset>
"""

RUN_CONFIG: dict = {"crawl": (PluginConfig("sitemap_xml"),)}


def known_urls(kb):
    return {url.url_string for url in kb.get_all_known_urls()}


class TestSitemap(PluginTest):

    target_url = TARGET_URL

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(TARGET_URL, "index"),
        MockResponse(SITEMAP_URL, SITEMAP, content_type="text/xml"),
        MockResponse(TARGET_URL + "hidden/", "hidden"),
    ]

    def test_sitemap(self):
        self._scan(self.target_url, RUN_CONFIG)

        self.assertEqual(
            known_urls(self.kb), {TARGET_URL, SITEMAP_URL, TARGET_URL + "hidden/"}
        )

    def test_long_desc(self):
        self.assertIn("sitemap.xml", sitemap_xml().get_long_desc())


class TestSitemapNotXML(PluginTest):

    target_url = TARGET_URL

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(TARGET_URL, "index"),
        MockResponse(SITEMAP_URL, "plain text without the closing tag"),
    ]

    def test_ignores_response_without_urlset(self):
        self._scan(self.target_url, RUN_CONFIG)

        self.assertEqual(known_urls(self.kb), {TARGET_URL})


class TestSitemapNotFound(PluginTest):

    target_url = TARGET_URL

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(TARGET_URL, "index"),
        MockResponse(SITEMAP_URL, "Not found </urlset>", status=404),
    ]

    def test_ignores_404_response(self):
        self._scan(self.target_url, RUN_CONFIG)

        self.assertEqual(known_urls(self.kb), {TARGET_URL})


class TestSitemapInvalidXML(PluginTest):

    target_url = TARGET_URL

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(TARGET_URL, "index"),
        MockResponse(
            SITEMAP_URL, "<urlset><loc>broken</urlset>", content_type="text/xml"
        ),
    ]

    def test_sends_sitemap_but_ignores_broken_xml(self):
        self._scan(self.target_url, RUN_CONFIG)

        self.assertEqual(known_urls(self.kb), {TARGET_URL, SITEMAP_URL})
        self.assertNotIn(URL(TARGET_URL + "broken"), self.kb.get_all_known_urls())
