"""
test_phishtank.py

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

import csv
import os
import unittest
from pathlib import Path

import w3af.core.data.kb.knowledge_base as kb
from w3af import ROOT_PATH
from w3af.core.controllers.exceptions import BaseFrameworkException
from w3af.core.data.constants.severity import MEDIUM
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.request.fuzzable_request import FuzzableRequest
from w3af.plugins.crawl.phishtank import PHISHTANK_DB, phishtank

LOCAL_PHISHTANK_DB = os.path.join(
    ROOT_PATH, "plugins", "tests", "crawl", "phishtank", "local_index.csv"
)

# A 64 characters label can not be IDNA encoded, so resolving it fails
# locally without sending any DNS query
UNRESOLVABLE_URL = URL("http://" + "a" * 64 + ".com/")


def read_phishtank_entries(path):
    with open(path) as pt_fd:
        pt_csv_reader = csv.reader(
            pt_fd,
            delimiter=" ",
            quotechar="|",
            quoting=csv.QUOTE_MINIMAL,
        )
        return list(pt_csv_reader)


def drain(output_queue):
    items = []
    while not output_queue.empty():
        items.append(output_queue.get())
    return items


class TestPhishtank(unittest.TestCase):

    def setUp(self):
        kb.kb.cleanup()
        self.addCleanup(kb.kb.cleanup)

    def crawl(self, url, phishtank_db=LOCAL_PHISHTANK_DB):
        plugin = phishtank(phishtank_db=phishtank_db)
        plugin.set_knowledge_base(kb.kb)
        plugin.crawl(FuzzableRequest(url), "debugging-id")
        return plugin

    def test_phishtank_no_match_for_unresolvable_domain(self):
        plugin = self.crawl(UNRESOLVABLE_URL)

        self.assertEqual(kb.kb.get("phishtank", "phishtank"), [])
        self.assertEqual(drain(plugin.output_queue), [])

    def test_phishtank_match_ip_address(self):
        plugin = self.crawl(URL("http://127.0.0.1/"))

        found_urls = [fr.get_url().url_string for fr in drain(plugin.output_queue)]
        self.assertEqual(found_urls, ["http://127.0.0.1/phish/"])

        vulns = kb.kb.get("phishtank", "phishtank")
        self.assertEqual(len(vulns), 1, vulns)

        vuln = vulns[0]
        self.assertEqual(vuln.get_name(), "Phishing scam")
        self.assertEqual(vuln.get_severity(), MEDIUM)
        self.assertEqual(vuln.get_url().url_string, "http://127.0.0.1/phish/")
        self.assertIn("phish_id=3", vuln.get_desc())

    def test_phishtank_matches_subdomains_only(self):
        plugin = phishtank(phishtank_db=LOCAL_PHISHTANK_DB)

        matches = plugin._is_in_phishtank({"example.org"})

        self.assertEqual(
            [(m.url.url_string, m.more_info_url.url_string) for m in matches],
            [
                (
                    "http://secure.example.org/bank/",
                    "http://www.phishtank.com/phish_detail.php?phish_id=4",
                )
            ],
        )

    def test_missing_database_raises(self):
        with self.assertRaises(BaseFrameworkException):
            self.crawl(URL("http://localhost/"), phishtank_db="/nonexistent/db.csv")

    def test_total_urls(self):
        total_lines = len(Path(PHISHTANK_DB).read_text().split("\n"))
        self.assertGreater(total_lines, 5000)

    def test_bundled_database_matches_first_and_last_entries(self):
        entries = read_phishtank_entries(PHISHTANK_DB)

        for phishing_url, detail_url in (entries[0], entries[-1]):
            domain = URL(phishing_url).get_domain()

            matches = phishtank()._is_in_phishtank({domain})

            self.assertIn(
                (phishing_url, detail_url),
                {(m.url.url_string, m.more_info_url.url_string) for m in matches},
            )

    def test_long_description_mentions_database(self):
        self.assertIn("phishtank database", phishtank().get_long_desc())
