"""
test_dot_net_errors.py

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

import unittest
from typing import ClassVar

from w3af.core.data.kb.knowledge_base import DBKnowledgeBase
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.request.fuzzable_request import FuzzableRequest
from w3af.plugins.infrastructure.dot_net_errors import dot_net_errors
from w3af.plugins.tests.canned_http_server import CannedReply
from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest
from w3af.plugins.tests.infrastructure.canned_plugin_test import (
    CannedServerPluginTest,
)


class TestDotNetErrors(PluginTest):

    target_url = "http://httpretty"

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(
            "http://httpretty/",
            body='<a href="sample.aspx">sample</a>',
            method="GET",
            status=200,
        ),
        MockResponse(
            "http://httpretty/sample.aspx", body="Hello world", method="GET", status=200
        ),
        MockResponse(
            "http://httpretty/sample~.aspx",
            body="<h2> <i>Runtime Error</i> </h2></span>...",
            method="GET",
            status=200,
        ),
    ]

    _run_configs: ClassVar[dict] = {
        "cfg": {
            "target": target_url,
            "plugins": {
                "infrastructure": (PluginConfig("dot_net_errors"),),
                "crawl": (
                    PluginConfig(
                        "web_spider",
                        ("only_forward", True, PluginConfig.BOOL),
                    ),
                ),
            },
        }
    }

    def test_dot_net_errors(self):
        cfg = self._run_configs["cfg"]
        self._scan(cfg["target"], cfg["plugins"])

        infos = self.kb.get("dot_net_errors", "dot_net_errors")

        self.assertEqual(len(infos), 1, infos)

        info = infos[0]

        self.assertEqual(info.get_name(), "Information disclosure via .NET errors")


class TestDotNetErrorsWithColonInURL(PluginTest):

    target_url = "http://httpretty"

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(
            "http://httpretty/",
            body='<a href="sample%3a.aspx">sample</a>',
            method="GET",
            status=200,
        ),
        MockResponse(
            "http://httpretty/sample.aspx", body="Hello world", method="GET", status=200
        ),
        MockResponse(
            "http://httpretty/sample~.aspx",
            body="<h2> <i>Runtime Error</i> </h2></span>...",
            method="GET",
            status=200,
        ),
    ]

    _run_configs: ClassVar[dict] = {
        "cfg": {
            "target": target_url,
            "plugins": {
                "infrastructure": (PluginConfig("dot_net_errors"),),
                "crawl": (
                    PluginConfig(
                        "web_spider",
                        ("only_forward", True, PluginConfig.BOOL),
                    ),
                ),
            },
        }
    }

    def test_dot_net_errors_with_colon_in_url(self):
        #
        # This test is here to check that no exceptions are raised in
        # dot_net_errors._generate_urls() while url-joining the filename that
        # contains the colon (sample%3a.aspx above)
        #
        cfg = self._run_configs["cfg"]
        self._scan(cfg["target"], cfg["plugins"])

        infos = self.kb.get("dot_net_errors", "dot_net_errors")
        self.assertEqual(len(infos), 0, infos)


class DotNetErrorsTest(CannedServerPluginTest):
    plugin_class = dot_net_errors

    def respond(self, request):
        body = dot_net_errors.RUNTIME_ERROR + dot_net_errors.REMOTE_MACHINE
        return CannedReply(500, {"Content-Type": "text/html"}, body)


class TestCustomErrorsEnabled(DotNetErrorsTest):
    def test_error_without_details_is_not_reported(self):
        self.plugin._send_and_check(URL("http://httpretty/sample~.aspx"))

        self.assertEqual(kb.get("dot_net_errors", "dot_net_errors"), [])

    def test_stops_after_max_tests(self):
        self.plugin.MAX_TESTS = 1
        self.plugin._already_tested.add(URL("http://httpretty/first.aspx"))

        self.plugin.discover(FuzzableRequest(URL("http://httpretty/second.aspx")), 1)

        self.assertEqual(self.server.requests, [])


class TestGenerateURLs(unittest.TestCase):
    def generate(self, url):
        return [u.url_string for u in dot_net_errors()._generate_urls(URL(url))]

    def test_special_chars_before_extension(self):
        self.assertEqual(
            self.generate("http://httpretty/a/default.aspx"),
            ["http://httpretty/a/default|.aspx", "http://httpretty/a/default~.aspx"],
        )

    def test_no_urls_without_filename_or_extension(self):
        self.assertEqual(self.generate("http://httpretty/a/"), [])
        self.assertEqual(self.generate("http://httpretty/README"), [])

    def test_filenames_with_colon_can_not_be_joined(self):
        self.assertEqual(self.generate("http://httpretty/sample:.aspx"), [])

    def test_runs_after_error_pages_grep(self):
        plugin = dot_net_errors()

        self.assertEqual(plugin.get_plugin_deps(), ["grep.error_pages"])
        self.assertIn("default~.aspx", plugin.get_long_desc())


kb = DBKnowledgeBase()
