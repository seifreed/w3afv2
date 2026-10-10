"""
test_web_diff.py

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
import tempfile
import unittest
from pathlib import Path
from typing import ClassVar

import w3af.core.controllers.output_manager as om
import w3af.core.data.kb.config as cf
from w3af import ROOT_PATH
from w3af.core.controllers.core_helpers.fingerprint_404 import (
    fingerprint_404_singleton,
)
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.request.fuzzable_request import FuzzableRequest
from w3af.core.exceptions import BaseFrameworkException
from w3af.plugins.crawl.web_diff import web_diff
from w3af.plugins.tests.canned_http_server import CannedReply
from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest
from w3af.plugins.tests.infrastructure.canned_plugin_test import (
    CannedServerPluginTest,
)
from w3af.plugins.tests.text_file_log import TextFileLog

LOCAL_DIR = os.path.join(ROOT_PATH, "plugins", "tests", "crawl", "web_diff")


def local_text(file_name):
    return Path(LOCAL_DIR, file_name).read_text()


class TestWebDiffScan(PluginTest):

    target_url = "http://moth/w3af/crawl/web_diff/"

    _run_configs: ClassVar[dict] = {
        "basic": {
            "target": target_url,
            "plugins": {
                "crawl": (
                    PluginConfig(
                        "web_diff",
                        ("content", True, PluginConfig.BOOL),
                        ("local_dir", LOCAL_DIR, PluginConfig.STR),
                        ("remote_url_path", URL(target_url), PluginConfig.URL),
                        ("banned_ext", "php,foo,bar", PluginConfig.LIST),
                    ),
                )
            },
        },
    }

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(target_url, "index of the remote directory"),
        MockResponse(target_url + "123.html", local_text("123.html")),
        MockResponse(target_url + "index.html", local_text("index.html")),
        MockResponse(target_url + "456.html", "remote content"),
        MockResponse(target_url + "exclude.php", "<?php echo 1; ?>"),
    ]

    def test_remote_files_are_sent_to_the_core(self):
        cfg = self._run_configs["basic"]
        self._scan(cfg["target"], cfg["plugins"])

        found_paths = {
            fr.get_url().get_path() for fr in self.kb.get_all_known_fuzzable_requests()
        }
        self.assertEqual(
            found_paths,
            {
                "/w3af/crawl/web_diff/",
                "/w3af/crawl/web_diff/123.html",
                "/w3af/crawl/web_diff/456.html",
                "/w3af/crawl/web_diff/exclude.php",
                "/w3af/crawl/web_diff/index.html",
            },
        )


class TestWebDiffReport(CannedServerPluginTest):

    plugin_class = web_diff

    REMOTE_ROOT = "http://w3af.org/remote/"
    SYMLINK_UNSUPPORTED = os.name == "nt"

    REMOTE_FILES: ClassVar[dict] = {
        "/remote/index.html": ("text/html", b"<html>index</html>\n"),
        "/remote/changed.html": ("text/html", b"<html>new</html>\n"),
        "/remote/LICENSE": ("text/plain", b"license"),
        "/remote/script.php": ("text/html", b"<?php echo 1; ?>"),
        "/remote/logo.bin": ("application/octet-stream", b"\xff\xfe\x00\x01"),
        "/remote/dangling.txt": ("text/plain", b"dangling"),
        "/remote/docs/guide.html": ("text/html", b"<html>guide</html>\n"),
    }

    def respond(self, request):
        content_type, body = self.REMOTE_FILES.get(
            request.path, ("text/html", b"Not found")
        )
        status = 200 if request.path in self.REMOTE_FILES else 404
        return CannedReply(status, {"Content-Type": content_type}, body)

    def setUp(self):
        fingerprint_404_singleton(om.out, cf.cf, cleanup=True)
        self.addCleanup(fingerprint_404_singleton, cleanup=True)

        super().setUp()

        local = tempfile.TemporaryDirectory()
        self.addCleanup(local.cleanup)
        self.local_dir = local.name
        self.build_local_tree()

        self.log = TextFileLog()
        self.addCleanup(self.log.remove)

    def build_local_tree(self):
        root = Path(self.local_dir)
        (root / "docs").mkdir()
        (root / "empty").mkdir()

        (root / "index.html").write_bytes(b"<html>index</html>\n")
        (root / "changed.html").write_bytes(b"<html>old</html>\n")
        (root / "gone.html").write_bytes(b"<html>gone</html>\n")
        (root / "LICENSE").write_bytes(b"license")
        (root / "script.php").write_bytes(b"<?php echo 2; ?>")
        (root / "logo.bin").write_bytes(b"\xff\xfe\x00\x01")
        (root / "docs" / "guide.html").write_bytes(b"<html>guide</html>\n")

        if not self.SYMLINK_UNSUPPORTED:
            (root / "dangling.txt").symlink_to(root / "does-not-exist.txt")

    def configure(self, content=True, local_dir=None, banned_ext=("php",)):
        options = self.plugin.get_options()
        options["content"].set_value(content)
        options["local_dir"].set_value(local_dir or self.local_dir)
        options["remote_url_path"].set_value(URL(self.REMOTE_ROOT))
        options["banned_ext"].set_value(list(banned_ext))
        self.plugin.set_options(options)

    def crawl(self):
        with self.log.attached_to_output_manager():
            self.plugin.crawl(FuzzableRequest(URL(self.REMOTE_ROOT)), "debugging-id")

    def drain_output_queue(self):
        urls = set()
        while not self.plugin.output_queue.empty():
            urls.add(self.plugin.output_queue.get().get_url().url_string)
        return urls

    def logged(self, message):
        return self.log.contains("information", message)

    def test_report_lists_every_comparison_result(self):
        self.configure()

        self.crawl()

        root = self.REMOTE_ROOT
        self.assertTrue(
            self.logged(
                "The following files exist in the local directory and in the"
                " remote server and their contents match:"
            )
        )
        for matching in ("index.html", "logo.bin", "docs/guide.html"):
            self.assertTrue(self.logged(f"- {root}{matching}"), matching)

        self.assertTrue(
            self.logged(
                "The following files exist in the local directory and in the"
                " remote server but their contents don't match:"
            )
        )
        self.assertTrue(self.logged(f"- {root}changed.html"))

        self.assertTrue(
            self.logged(
                "The following files exist in the local directory and do NOT"
                " exist in the remote server:"
            )
        )
        self.assertTrue(self.logged(f"- {root}gone.html"))

    def test_report_statistics_ignore_banned_extensions_and_unreadable_files(self):
        self.configure()

        self.crawl()

        existing = 6 if self.SYMLINK_UNSUPPORTED else 7
        self.assertTrue(self.logged(f"Match files: {existing} of {existing + 1}"))
        self.assertTrue(self.logged("Match contents: 3 of 4"))

    def test_text_responses_are_sent_to_the_core(self):
        self.configure()

        self.crawl()

        root = self.REMOTE_ROOT
        found = self.drain_output_queue()
        self.assertIn(f"{root}index.html", found)
        self.assertIn(f"{root}docs/guide.html", found)
        self.assertIn(f"{root}LICENSE", found)
        self.assertNotIn(f"{root}logo.bin", found)
        self.assertNotIn(f"{root}gone.html", found)

    def test_empty_directories_are_not_requested(self):
        self.configure()

        self.crawl()

        requested = {request.path for request in self.server.requests}
        self.assertNotIn("/remote/empty/", requested)
        self.assertIn("/remote/docs/guide.html", requested)

    def test_contents_are_not_compared_when_disabled(self):
        self.configure(content=False)

        self.crawl()

        existing = 6 if self.SYMLINK_UNSUPPORTED else 7
        self.assertTrue(self.logged(f"Match files: {existing} of {existing + 1}"))
        self.assertNotIn("Match contents", Path(self.log.path).read_text())
        self.assertEqual(self.plugin._eq_content, [])
        self.assertEqual(self.plugin._not_eq_content, [])

    def test_banned_extensions_are_not_compared(self):
        self.configure(banned_ext=())

        self.crawl()

        script_url = URL(f"{self.REMOTE_ROOT}script.php")
        self.assertIn(script_url, self.plugin._not_eq_content)

    def test_crawl_without_configuration_raises(self):
        with self.assertRaises(BaseFrameworkException):
            self.plugin.crawl(FuzzableRequest(URL(self.REMOTE_ROOT)), "debugging-id")

    def test_local_dir_must_be_a_directory(self):
        not_a_directory = os.path.join(self.local_dir, "index.html")

        with self.assertRaises(BaseFrameworkException):
            self.configure(local_dir=not_a_directory)

    def test_long_description_mentions_options(self):
        description = self.plugin.get_long_desc()

        for option_name in ("local_dir", "remote_url_path", "banned_ext", "content"):
            self.assertIn(option_name, description)


class TestWebDiffDefaults(unittest.TestCase):

    def test_options_default_to_php_asp_and_jsp_exclusion(self):
        options = web_diff().get_options()

        self.assertEqual(options["banned_ext"].get_value(), ["asp", "jsp", "php"])
        self.assertTrue(options["content"].get_value())
