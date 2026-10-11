"""
test_ghdb.py

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

import json
import os
import tempfile
import unittest
import urllib.parse
from pathlib import Path
from typing import ClassVar, cast

import w3af.core.controllers.output_manager as om
from w3af import ROOT_PATH
from w3af.core.data.constants import severity
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.request.fuzzable_request import FuzzableRequest
from w3af.core.exceptions import BaseFrameworkException
from w3af.plugins.crawl.ghdb import GoogleHack, ghdb
from w3af.plugins.tests.canned_http_server import CannedReply
from w3af.plugins.tests.infrastructure.canned_plugin_test import (
    CannedServerPluginTest,
    kb,
)

FIXTURES_DIR = os.path.join(ROOT_PATH, "plugins", "tests", "crawl", "ghdb")
SIGNATURES_FILE = os.path.join(FIXTURES_DIR, "signatures.xml")
DROPPER_FILE = os.path.join(FIXTURES_DIR, "dropper.xml")

# A public IP address: it is not a private site, and it does not need DNS
PUBLIC_TARGET = "http://8.8.8.8/"

HTML = {"Content-Type": "text/html"}


class GHDBCrawlTest(CannedServerPluginTest):
    """
    Runs the ghdb plugin against a canned Google (AJAX API and web pages) and
    a canned target site. The URL each search term finds is in FOUND_BY_TERM.
    """

    plugin_class = ghdb

    ghdb_file = SIGNATURES_FILE

    FOUND_BY_TERM: ClassVar[dict] = {
        "needle": [PUBLIC_TARGET + "leaked/"],
        "ghost": [PUBLIC_TARGET + "gone/"],
    }

    def setUp(self):
        super().setUp()
        plugin = cast(ghdb, self.plugin)
        plugin._ghdb_file = self.ghdb_file

    def respond(self, request):
        uri = urllib.parse.urlsplit(request.uri)

        if uri.hostname == "ajax.googleapis.com":
            return self.respond_ajax_search(uri)

        if uri.hostname == "www.google.com":
            return CannedReply(200, HTML, "<html><body>no results</body></html>")

        return self.respond_target_site(request.path)

    def respond_ajax_search(self, uri):
        query = dict(urllib.parse.parse_qsl(uri.query))
        term = query["q"].rpartition(" ")[2]

        results = []
        if query["start"] == "0":
            results = [{"url": url} for url in self.FOUND_BY_TERM.get(term, [])]

        body = json.dumps({"responseStatus": 200, "responseData": {"results": results}})
        return CannedReply(200, {"Content-Type": "application/json"}, body)

    def respond_target_site(self, path):
        if path in ("/", "/leaked/"):
            return CannedReply(200, HTML, "leaked sensitive information")

        return CannedReply(404, HTML, "Not found")

    def crawl(self, url=PUBLIC_TARGET):
        plugin = cast(ghdb, self.plugin)
        plugin.crawl(FuzzableRequest(URL(url)), "debugging-id")

    def requested_hosts(self):
        return {urllib.parse.urlsplit(r.uri).hostname for r in self.server.requests}

    def found_urls(self):
        urls = set()
        while not self.plugin.output_queue.empty():
            urls.add(self.plugin.output_queue.get().get_url().url_string)
        return urls


class TestGHDBMatch(GHDBCrawlTest):

    def test_ghdb_match(self):
        self.crawl()

        vulns = kb.get("ghdb", "vuln")
        self.assertEqual(len(vulns), 1, vulns)

        vuln = vulns[0]
        self.assertEqual(vuln.get_url().url_string, PUBLIC_TARGET + "leaked/")
        self.assertEqual(vuln.get_severity(), severity.MEDIUM)
        self.assertEqual(vuln.get_name(), "Google hack database match")
        self.assertIn("A needle in a haystack", vuln.get_desc(with_id=False))

    def test_matching_page_is_sent_to_the_core(self):
        self.crawl()

        self.assertEqual(self.found_urls(), {PUBLIC_TARGET + "leaked/"})

    def test_every_valid_signature_is_searched(self):
        self.crawl()

        searched_terms = {
            dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(r.uri).query))["q"]
            for r in self.server.requests
            if "ajax.googleapis.com" in r.uri
        }
        self.assertEqual(
            searched_terms,
            {
                "site:8.8.8.8 needle",
                "site:8.8.8.8 ghost",
                "site:8.8.8.8 nodesc",
            },
        )


class TestGHDBPrivateSite(GHDBCrawlTest):

    def test_ghdb_private(self):
        self.crawl("http://127.0.0.1/")

        self.assertEqual(kb.get("ghdb", "vuln"), [])
        self.assertEqual(self.server.requests, [])


class TestGHDBRequestFailure(GHDBCrawlTest):

    ghdb_file = DROPPER_FILE

    FOUND_BY_TERM: ClassVar[dict] = {"dropper": [PUBLIC_TARGET + "dead/"]}

    def respond_target_site(self, path):
        raise ConnectionResetError

    def test_result_that_can_not_be_requested_is_not_reported(self):
        self.crawl()

        self.assertEqual(kb.get("ghdb", "vuln"), [])
        self.assertEqual(self.found_urls(), set())


class TestGHDBDatabase(unittest.TestCase):

    def setUp(self):
        self.plugin = ghdb()
        self.plugin.set_output(om.out)
        self.addCleanup(self.plugin.end)

    def read_ghdb_from(self, xml_content):
        ghdb_dir = tempfile.TemporaryDirectory()
        self.addCleanup(ghdb_dir.cleanup)

        ghdb_path = os.path.join(ghdb_dir.name, "ghdb.xml")
        Path(ghdb_path).write_text(xml_content, encoding="utf-8")

        self.plugin._ghdb_file = ghdb_path
        return self.plugin._read_ghdb()

    def test_xml_parsing(self):
        ghdb_set = self.plugin._read_ghdb()

        self.assertGreater(len(ghdb_set), 300)

        for ghdb_inst in ghdb_set:
            self.assertIsInstance(ghdb_inst, GoogleHack)

    def test_corrupt_signatures_are_skipped(self):
        self.plugin._ghdb_file = SIGNATURES_FILE

        google_hacks = self.plugin._read_ghdb()

        self.assertEqual(
            [(gh.search, gh.desc) for gh in google_hacks],
            [
                ("needle", "A needle in a haystack"),
                ("ghost", "A page that no longer exists"),
                ("nodesc", "No description provided by GHDB."),
            ],
        )

    def test_missing_database_raises(self):
        self.plugin._ghdb_file = os.path.join(FIXTURES_DIR, "missing.xml")

        with self.assertRaises(BaseFrameworkException):
            self.plugin._read_ghdb()

    def test_malformed_database_raises(self):
        with self.assertRaises(BaseFrameworkException):
            self.read_ghdb_from("<searchEngineSignature><signature>")

    def test_database_with_entities_is_rejected(self):
        xml_content = (
            '<?xml version="1.0"?><!DOCTYPE bomb [<!ENTITY a "aaaa">]>'
            "<searchEngineSignature>&a;</searchEngineSignature>"
        )

        with self.assertRaises(BaseFrameworkException):
            self.read_ghdb_from(xml_content)

    def test_google_hacks_with_the_same_search_are_equal(self):
        first = GoogleHack("inurl:admin", "Admin pages")
        second = GoogleHack("inurl:admin", "Another description")

        self.assertEqual(first, second)
        self.assertEqual(len({first, second}), 1)

    def test_result_limit_option_round_trip(self):
        options = self.plugin.get_options()
        self.assertEqual(options["result_limit"].get_value(), 300)

        options["result_limit"].set_value(25)
        self.plugin.set_options(options)

        self.assertEqual(self.plugin.get_options()["result_limit"].get_value(), 25)

    def test_long_description_credits_exploit_db(self):
        self.assertIn("Exploit-DB", self.plugin.get_long_desc())
