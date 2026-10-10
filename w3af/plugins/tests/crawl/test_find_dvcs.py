"""
test_find_dvcs.py

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

import os
import re
import struct
import unittest
from pathlib import Path
from typing import ClassVar

import w3af.core.data.kb.knowledge_base as kb
from w3af import ROOT_PATH
from w3af.core.data.constants import severity
from w3af.core.filesystem import create_temp_dir
from w3af.plugins.crawl.find_dvcs import find_dvcs
from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest

BASE_URL = "http://mock/w3af/crawl/find_dvcs/"

RUN_PLUGINS = {
    "crawl": (
        PluginConfig("find_dvcs"),
        PluginConfig("web_spider", ("only_forward", True, PluginConfig.BOOL)),
    )
}


def build_git_index(version, *filenames):
    entry_header_len = {2: 62, 3: 63}.get(version, 62)
    entries = b""

    for filename in filenames:
        padding = 8 - ((entry_header_len + len(filename)) % 8)
        entries += (
            b"\x00" * (entry_header_len - 1)
            + bytes([len(filename)])
            + filename
            + b"\x00" * padding
        )

    return b"DIRC" + struct.pack(">II", version, len(filenames)) + entries


def build_hg_dirstate(*filenames):
    entries = b"".join(
        struct.pack(">I", len(filename)) + filename + b"\x00" * 13
        for filename in filenames
    )
    return b"\x00" * 53 + entries


def build_bzr_dirstate(filename):
    fields = [
        b"#bazaar dirstate flat format 3",
        b"",
        filename,
        b"x",
        b"f",
        b"",
        b"",
        b"y",
        b"d",
    ]
    return b"\x00".join(fields)


def build_svn_entries(filename, dirname):
    lines = (
        [b"10"]
        + [b""] * 27
        + [filename, b"file"]
        + [b""] * 32
        + [dirname, b"dir"]
        + [b"", b"junk-name", b"junk"]
    )
    return b"\n".join(lines)


CVS_ENTRIES = (
    b"/cvs-file.txt/1.1/Sun Apr  7 01:29:26 1996//\n"
    b"D/somedir////\n"
    b"/no-colons.txt/1.1/dummy timestamp//\n"
    b"/short/line\n"
)

GITIGNORE = b"# Ignored files\ngit-ignored.txt\nsub/../git-ignored.txt\n"

EXISTING_FILE_RE = re.compile(
    re.escape(BASE_URL) + r"((git|hg|bzr|svn|cvs)-(file\.txt|dir)|git-ignored\.txt)$"
)


class TestFindDVCS(PluginTest):

    target_url = BASE_URL

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(
            BASE_URL,
            '<a href="index.php">index</a><a href="sub/page.html">sub</a>',
        ),
        MockResponse(BASE_URL + "index.php", "Index"),
        MockResponse(BASE_URL + "sub/page.html", "Sub page"),
        MockResponse(BASE_URL + ".git/index", build_git_index(2, b"git-file.txt")),
        MockResponse(BASE_URL + ".gitignore", GITIGNORE),
        MockResponse(BASE_URL + ".hg/dirstate", build_hg_dirstate(b"hg-file.txt")),
        MockResponse(BASE_URL + ".hgignore", "<html>\n</html>"),
        MockResponse(
            BASE_URL + ".bzr/checkout/dirstate", build_bzr_dirstate(b"bzr-file.txt")
        ),
        MockResponse(
            BASE_URL + ".bzrignore",
            "Moved",
            status=302,
            headers={"Location": BASE_URL},
        ),
        MockResponse(
            BASE_URL + ".svn/entries", build_svn_entries(b"svn-file.txt", b"svn-dir")
        ),
        MockResponse(BASE_URL + ".svn/wc.db", b"This is not a database"),
        MockResponse(BASE_URL + ".svnignore", ""),
        MockResponse(BASE_URL + "CVS/Entries", CVS_ENTRIES),
        MockResponse(BASE_URL + "sub/.git/index", b"DIRC\x00\x00\x00\x02"),
        MockResponse(BASE_URL + "sub/.svn/entries", b"12\n"),
        MockResponse(EXISTING_FILE_RE, "Exists"),
    ]

    FOUND_REPOS = (
        "git repository",
        "git ignore",
        "hg repository",
        "bzr repository",
        "svn repository",
        "cvs repository",
    )

    MISSING_REPOS = (
        "hg ignore",
        "bzr ignore",
        "svn repository db",
        "svn ignore",
        "cvs ignore",
    )

    def test_dvcs(self):
        self._scan(self.target_url, RUN_PLUGINS)

        for repo in self.FOUND_REPOS:
            vulns_for_repo = self.kb.get("find_dvcs", repo)
            self.assertEqual(len(vulns_for_repo), 1, f"Failed at {repo}")

            vuln_repo = vulns_for_repo[0]
            self.assertTrue(vuln_repo.get_url().url_string.startswith(BASE_URL))
            self.assertEqual(vuln_repo.get_severity(), severity.MEDIUM)
            self.assertEqual(vuln_repo.get_name(), "Source code repository")
            self.assertIn(repo, vuln_repo.get_desc().lower())

        for repo in self.MISSING_REPOS:
            self.assertEqual(self.kb.get("find_dvcs", repo), [], repo)

        known_files = {u.get_file_name() for u in self.kb.get_all_known_urls()}
        expected_files = {
            "git-file.txt",
            "git-ignored.txt",
            "hg-file.txt",
            "bzr-file.txt",
            "svn-file.txt",
            "svn-dir",
            "cvs-file.txt",
        }
        self.assertEqual(expected_files - known_files, set())


class TestFindDVCSParsers(unittest.TestCase):
    def setUp(self):
        self.fdvcs = find_dvcs()

    def test_ignore_file_blank(self):
        self.assertEqual(self.fdvcs.ignore_file(""), set())

    def test_ignore_file_two_files_comment(self):
        content = """# Ignore these files
        foo.txt
        bar*
        spam.eggs
        """
        files = self.fdvcs.ignore_file(content)

        self.assertEqual(files, {"foo.txt", "bar", "spam.eggs"})

    def test_ignore_file_anchors_and_false_positives(self):
        content = b"^/anchored$\ndir/\nwith space\n*\n"

        self.assertEqual(self.fdvcs.ignore_file(content), {"/anchored", "dir"})

    def test_ignore_file_html(self):
        self.assertEqual(self.fdvcs.ignore_file(b"<html>"), set())

    def test_git_index_v2(self):
        body = build_git_index(2, b"a.txt", b"dir/b.php")

        self.assertEqual(self.fdvcs.git_index(body), {b"a.txt", b"dir/b.php"})

    def test_git_index_v3(self):
        body = build_git_index(3, b"c.txt")

        self.assertEqual(self.fdvcs.git_index(body), {b"c.txt"})

    def test_git_index_unsupported_version(self):
        self.assertEqual(self.fdvcs.git_index(build_git_index(4, b"a.txt")), set())

    def test_git_index_bad_signature(self):
        self.assertEqual(self.fdvcs.git_index(b"NOPE" + b"\x00" * 20), set())

    def test_git_index_truncated_entry(self):
        body = build_git_index(2, b"a.txt")[:-10]

        self.assertEqual(self.fdvcs.git_index(body), set())

    def test_hg_dirstate(self):
        body = build_hg_dirstate(b"a.txt", b"b.txt")

        self.assertEqual(self.fdvcs.hg_dirstate(body), {b"a.txt", b"b.txt"})

    def test_hg_dirstate_truncated_entry(self):
        body = b"\x00" * 53 + struct.pack(">I", 100) + b"short"

        self.assertEqual(self.fdvcs.hg_dirstate(body), set())

    def test_bzr_dirstate(self):
        body = build_bzr_dirstate(b"a.txt")

        self.assertEqual(self.fdvcs.bzr_checkout_dirstate(body), {b"a.txt"})

    def test_bzr_dirstate_bad_header(self):
        self.assertEqual(self.fdvcs.bzr_checkout_dirstate(b"not bazaar"), set())

    def test_svn_entries(self):
        body = build_svn_entries(b"a.txt", b"subdir")

        self.assertEqual(self.fdvcs.svn_entries(body), {b"a.txt", b"subdir"})

    def test_svn_entries_placeholder(self):
        self.assertEqual(self.fdvcs.svn_entries(b"12\n"), set())

    def test_svn_wc_db_invalid(self):
        create_temp_dir()
        self.assertEqual(self.fdvcs.svn_wc_db(b"This is not a database"), set())

    def test_cvs_entries(self):
        self.assertEqual(self.fdvcs.cvs_entries(CVS_ENTRIES), {b"cvs-file.txt"})

    def test_clean_filenames(self):
        filenames = {b"/a.txt", "./b.txt", "c/", b"\xff\xfed.txt"}

        self.assertEqual(
            self.fdvcs._clean_filenames(filenames), {"a.txt", "b.txt", "c", "d.txt"}
        )

    def test_long_description(self):
        self.assertIn("repositories", self.fdvcs.get_long_desc())


class TestSVN(PluginTest):

    WC_DB = Path(
        os.path.join(
            ROOT_PATH, "plugins", "tests", "crawl", "find_dvcs", "sample-wc.db"
        )
    ).read_bytes()

    CONTENT = "Fixture contents here!"

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse("http://mock/", "root"),
        MockResponse("http://mock/.svn/wc.db", WC_DB),
        MockResponse(
            "http://mock/.svn/pristine/96/96acedb8cc77c893b90d1ce37c7119fd0c0fba00.svn-base",
            CONTENT,
        ),
        MockResponse("http://mock/seris/changelog.rst", CONTENT),
    ]

    target_url = "http://mock"

    def test_wc_db(self):
        self._scan(self.target_url, RUN_PLUGINS)

        url_list = kb.kb.get_all_known_urls()

        self.assertEqual(
            {u.url_string for u in url_list}, {m.url for m in self.MOCK_RESPONSES}
        )

        vulns = self.kb.get("find_dvcs", "svn repository db")
        self.assertEqual(len(vulns), 1, vulns)
