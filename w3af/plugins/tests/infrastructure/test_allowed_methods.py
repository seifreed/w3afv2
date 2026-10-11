"""
test_allowed_methods.py

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
import unittest
from typing import ClassVar

import pytest

from w3af.core.data.kb.knowledge_base import DBKnowledgeBase
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.request.fuzzable_request import FuzzableRequest
from w3af.core.exceptions import RunOnce
from w3af.plugins.infrastructure.allowed_methods import allowed_methods
from w3af.plugins.tests.canned_http_server import CannedReply
from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest
from w3af.plugins.tests.infrastructure.canned_plugin_test import (
    CannedServerPluginTest,
)

DAV_ROOT = "http://dav/"
DAV_PAGES = {DAV_ROOT, DAV_ROOT + "index.html", DAV_ROOT + "a/", DAV_ROOT + "b/"}


class AnyMethodResponse(MockResponse):
    """
    Answers requests sent with any HTTP method, including the non-standard
    ones (ARGENTINA, PROPFIND, ...) that allowed_methods sends.
    """

    def matches(self, http_request, uri):
        return self.url_matches(uri)


def _same_response_for_every_method(mock_response, request, uri, headers):
    headers["Content-Type"] = "text/html"
    return 200, headers, "<html><body>Hello world</body></html>"


def _only_get_and_post(mock_response, request, uri, headers):
    headers["Content-Type"] = "text/html"
    if request.command in ("GET", "POST"):
        return 200, headers, "<html><body>Hello world</body></html>"
    return 403, headers, "Forbidden"


def _dav_directory(mock_response, request, uri, headers):
    headers["Content-Type"] = "text/html"

    if request.command == "OPTIONS":
        headers["Allow"] = "GET, HEAD, PROPFIND"
        headers["Public"] = "OPTIONS, MKCOL"
        return 200, headers, ""

    if request.command in ("GET", "HEAD"):
        if request.uri not in DAV_PAGES:
            return 404, headers, "Not found"
        body = '<a href="/a/">a</a><a href="/b/">b</a><a href="index.html">i</a>'
        return 200, headers, body

    if request.command == "SEARCH":
        raise ConnectionResetError("Unsupported method")

    return 405, headers, "Method not allowed"


class TestAllowedMethods(PluginTest):
    """
    The allowed_methods plugin sends custom/special HTTP methods through
    ExtendedUrllib, these scans make sure that works end to end.
    """

    target_url = "http://apache/"

    MOCK_RESPONSES: ClassVar[list] = [
        AnyMethodResponse(re.compile(".*"), body=_same_response_for_every_method)
    ]

    plugins: ClassVar[dict] = {
        "infrastructure": (PluginConfig("allowed_methods"),),
    }

    @pytest.mark.smoke
    def test_non_existent_methods_default_to_get(self):
        self._scan(self.target_url, self.plugins)

        infos = self.kb.get("allowed_methods", "custom-configuration")

        self.assertEqual(len(infos), 1, infos)
        info = infos[0]

        msg = "The remote Web server has a custom configuration, in which any"
        self.assertTrue(info.get_desc().startswith(msg))
        self.assertEqual(info.get_name(), "Non existent methods default to GET")

        self.assertEqual(self.kb.get("allowed_methods", "methods"), [])


class TestAllowedMethodsRewriteRules(PluginTest):
    r"""
    A server configured to forbid everything but GET and POST:
        RewriteEngine on
        RewriteCond %{THE_REQUEST} !^(POST|GET)\ /.*\ HTTP/1\.1$
        RewriteRule .* - [F]
    """

    target_url = "http://modsecurity/"

    MOCK_RESPONSES: ClassVar[list] = [
        AnyMethodResponse(re.compile(".*"), body=_only_get_and_post)
    ]

    plugins: ClassVar[dict] = {
        "infrastructure": (
            PluginConfig("allowed_methods", ("dav_only", False, PluginConfig.BOOL)),
        ),
    }

    def test_bruteforce_finds_get_and_post(self):
        self._scan(self.target_url, self.plugins)

        self.assertEqual(self.kb.get("allowed_methods", "custom-configuration"), [])

        infos = self.kb.get("allowed_methods", "methods")
        self.assertEqual(len(infos), 1, infos)
        self.assertEqual(infos[0].get_name(), "Allowed HTTP methods")
        self.assertEqual(infos[0]["methods"], ["GET", "POST"])


class TestAllowedMethodsDAV(PluginTest):

    target_url = DAV_ROOT

    MOCK_RESPONSES: ClassVar[list] = [
        AnyMethodResponse(re.compile(".*"), body=_dav_directory)
    ]

    plugins: ClassVar[dict] = {
        "infrastructure": (
            PluginConfig("allowed_methods", ("run_once", False, PluginConfig.BOOL)),
        ),
        "crawl": (PluginConfig("web_spider"),),
    }

    def test_dav_methods_in_every_directory(self):
        self._scan(self.target_url, self.plugins)

        infos = self.kb.get("allowed_methods", "dav-methods")
        urls = {i.get_url().url_string for i in infos}

        self.assertEqual(urls, {DAV_ROOT, DAV_ROOT + "a/", DAV_ROOT + "b/"})

        for info in infos:
            self.assertEqual(info.get_name(), "DAV methods enabled")
            self.assertEqual(
                info["methods"], ["GET", "HEAD", "MKCOL", "OPTIONS", "PROPFIND"]
            )


class AllowedMethodsTest(CannedServerPluginTest):
    plugin_class = allowed_methods


class TestOnlyArgentinaFails(AllowedMethodsTest):
    def respond(self, request):
        if request.command == "ARGENTINA":
            raise ConnectionResetError("Unsupported method")
        return CannedReply(200, {}, "Hello world")

    def test_can_bruteforce(self):
        self.assertTrue(self.plugin._can_bruteforce(URL(DAV_ROOT)))


class TestOnlyGetFails(AllowedMethodsTest):
    def respond(self, request):
        if request.command == "GET":
            raise ConnectionResetError("Broken GET")
        return CannedReply(200, {}, "Hello world")

    def test_can_not_bruteforce(self):
        self.assertFalse(self.plugin._can_bruteforce(URL(DAV_ROOT)))


class TestEveryRequestFails(AllowedMethodsTest):
    def respond(self, request):
        raise ConnectionResetError("Down")

    def test_no_methods_identified(self):
        self.assertEqual(self.plugin._identify_allowed_methods(URL(DAV_ROOT)), ([], []))


class TestRunOnce(AllowedMethodsTest):
    def respond(self, request):
        return CannedReply(405, {}, "Method not allowed")

    def test_second_discover_raises_run_once(self):
        fuzzable_request = FuzzableRequest(URL(DAV_ROOT))

        self.plugin.discover(fuzzable_request, 1)

        self.assertRaises(RunOnce, self.plugin.discover, fuzzable_request, 2)
        self.assertEqual(kb.get("allowed_methods", "methods"), [])


class TestEnd(unittest.TestCase):
    def setUp(self):
        kb.cleanup()
        self.addCleanup(kb.cleanup)
        self.plugin = allowed_methods()
        self.plugin.set_knowledge_base(kb)

    def test_reports_dav_methods_grouped_by_url(self):
        self.plugin._analyze_methods(URL(DAV_ROOT), ["GET", "PROPFIND"], [1])
        self.plugin._analyze_methods(URL(DAV_ROOT + "a/"), ["MKCOL"], [2])

        self.plugin.end()

        self.assertEqual(len(kb.get("allowed_methods", "dav-methods")), 2)

    def test_options_round_trip(self):
        options = self.plugin.get_options()
        options["run_once"].set_value(False)
        options["dav_only"].set_value(False)

        self.plugin.set_options(options)

        self.assertFalse(self.plugin._exec_one_time)
        self.assertFalse(self.plugin._report_dav_only)

    def test_long_description(self):
        self.assertIn("run_once", self.plugin.get_long_desc())


kb = DBKnowledgeBase()
