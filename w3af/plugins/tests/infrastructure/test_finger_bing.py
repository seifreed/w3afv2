"""
test_finger_bing.py

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
from w3af.plugins.infrastructure.finger_bing import finger_bing
from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest
from w3af.plugins.tests.search_engine_pages import bing_search_response

CONTACT_URL = "http://www.bonsai-sec.com/en/contact/"
BLOG_URL = "http://blog.example.org/2011/pentest-team/"
LOGO_URL = "http://www.bonsai-sec.com/logo.png"
PUBLIC_IP_URL = "http://8.8.8.8/"


class TestFingerBing(PluginTest):

    target_url = "http://www.bonsai-sec.com/"

    MOCK_RESPONSES: ClassVar[list] = [
        bing_search_response([CONTACT_URL, BLOG_URL, LOGO_URL]),
        MockResponse(
            CONTACT_URL,
            "<html><body>"
            '<a href="mailto:info@bonsai-sec.com">Write us</a>'
            '<a href="mailto:andres@bonsai-sec.com">Andres</a>'
            "</body></html>",
        ),
        MockResponse(
            BLOG_URL,
            "<html><body>"
            '<a href="mailto:andres@bonsai-sec.com">Andres</a>'
            '<a href="mailto:someone@example.org">Someone</a>'
            "</body></html>",
        ),
        MockResponse(LOGO_URL, b"\x89PNG\r\n\x1a\n", content_type="image/png"),
    ]

    def create_plugin(self):
        plugin = finger_bing()
        plugin.set_url_opener(self.w3afcore.uri_opener)
        plugin.set_worker_pool(self.w3afcore.worker_pool)
        plugin.set_knowledge_base(self.kb)
        return plugin

    def test_search_accounts_finds_domain_emails(self):
        self.create_plugin().search_accounts(URL(self.target_url))

        emails = self.kb.get("emails", "emails")

        self.assertEqual(
            {(e["mail"], e["user"]) for e in emails},
            {
                ("info@bonsai-sec.com", "info"),
                ("andres@bonsai-sec.com", "andres"),
            },
        )
        self.assertEqual(
            {e.get_name() for e in emails},
            {"Email account"},
        )

        bing_queries = [r.uri for r in self.received_requests if "bing.com" in r.uri]
        self.assertIn(
            "http://www.bing.com/search?q=%40bonsai-sec.com&first=1&FORM=PERE",
            bing_queries,
        )

    def test_discover_searches_public_site(self):
        plugins = {
            "infrastructure": (
                PluginConfig("finger_bing", ("result_limit", 10, PluginConfig.INT)),
            )
        }
        self._scan(PUBLIC_IP_URL, plugins)

        bing_queries = [r.uri for r in self.received_requests if "bing.com" in r.uri]
        self.assertEqual(
            bing_queries,
            [
                "http://www.bing.com/search?q=%408.8.8.8&first=1&FORM=PERE",
                "http://www.bing.com/search?q=%408.8.8.8&first=11&FORM=PERE",
            ],
        )
        self.assertEqual(self.kb.get("emails", "emails"), [])

    def test_discover_ignores_private_site(self):
        plugins = {"infrastructure": (PluginConfig("finger_bing"),)}
        self._scan("http://127.0.0.1/", plugins)

        bing_queries = [r.uri for r in self.received_requests if "bing.com" in r.uri]
        self.assertEqual(bing_queries, [])

    def test_long_description(self):
        self.assertIn("result_limit", finger_bing().get_long_desc())
