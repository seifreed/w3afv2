"""
test_finger_google.py

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
from w3af.plugins.infrastructure.finger_google import finger_google
from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest
from w3af.plugins.tests.search_engine_pages import google_search_responses

CONTACT_URL = "http://www.w3af.org/contact/"
MIRROR_URL = "http://mirror.example.org/w3af/"
LOGO_URL = "http://www.w3af.org/logo.png"
PUBLIC_IP_URL = "http://8.8.8.8/"

SNIPPET_EMAILS = (
    '<span class="st"><a href="mailto:press@w3af.org">press@w3af.org</a>'
    '<a href="mailto:x3d@example.org">x3d@example.org</a></span>'
)


class TestFingerGoogle(PluginTest):

    target_url = "http://www.w3af.org/"

    MOCK_RESPONSES: ClassVar[list] = [
        *google_search_responses(
            [CONTACT_URL, MIRROR_URL, LOGO_URL], extra_html=SNIPPET_EMAILS
        ),
        MockResponse(
            CONTACT_URL,
            "<html><body>"
            '<a href="mailto:andres@w3af.org">Andres</a>'
            '<a href="mailto:info@w3af.org">Info</a>'
            "</body></html>",
        ),
        MockResponse(
            MIRROR_URL,
            "<html><body>"
            '<a href="mailto:andres@w3af.org">Andres</a>'
            '<a href="mailto:mirror@w3af.org">Mirror</a>'
            '<a href="mailto:x3d@example.org">x3d</a>'
            "</body></html>",
        ),
        MockResponse(LOGO_URL, b"\x89PNG\r\n\x1a\n", content_type="image/png"),
    ]

    def create_plugin(self, fast_search=False):
        plugin = finger_google()
        plugin.set_url_opener(self.w3afcore.uri_opener)
        plugin.set_worker_pool(self.w3afcore.worker_pool)

        options = plugin.get_options()
        options["result_limit"].set_value(20)
        options["fast_search"].set_value(fast_search)
        plugin.set_options(options)

        return plugin

    def found_accounts(self):
        return {(e["mail"], e["user"]) for e in self.kb.get("emails", "emails")}

    def google_requests(self):
        return [r.uri for r in self.received_requests if "google" in r.uri]

    def test_complete_search_visits_results(self):
        self.create_plugin().search_accounts(URL(self.target_url))

        self.assertEqual(
            self.found_accounts(),
            {
                ("andres@w3af.org", "andres"),
                ("info@w3af.org", "info"),
                ("mirror@w3af.org", "mirror"),
            },
        )

        emails = self.kb.get("emails", "emails")
        self.assertEqual(len(emails), 3, emails)
        self.assertEqual({e.get_name() for e in emails}, {"Email account"})
        self.assertEqual(
            {e.get_url().url_string for e in emails},
            {CONTACT_URL, MIRROR_URL},
        )

    def test_fast_search_reads_result_pages(self):
        self.create_plugin(fast_search=True).search_accounts(URL(self.target_url))

        self.assertEqual(self.found_accounts(), {("press@w3af.org", "press")})

        visited = [r.uri for r in self.received_requests]
        self.assertNotIn(CONTACT_URL, visited)
        self.assertTrue(
            all("www.google.com/search?" in uri for uri in self.google_requests()),
            self.google_requests(),
        )

    def test_discover_searches_public_site(self):
        plugins = {
            "infrastructure": (
                PluginConfig("finger_google", ("result_limit", 10, PluginConfig.INT)),
            )
        }
        self._scan(PUBLIC_IP_URL, plugins)

        self.assertIn(
            "http://ajax.googleapis.com/ajax/services/search/web?"
            "v=1.0&q=%408.8.8.8&rsz=8&start=0",
            self.google_requests(),
        )
        self.assertEqual(self.kb.get("emails", "emails"), [])

    def test_discover_ignores_private_site(self):
        plugins = {"infrastructure": (PluginConfig("finger_google"),)}
        self._scan("http://127.0.0.1/", plugins)

        self.assertEqual(self.google_requests(), [])

    def test_long_description(self):
        self.assertIn("fast_search", finger_google().get_long_desc())
