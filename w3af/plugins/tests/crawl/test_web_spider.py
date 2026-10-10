"""
test_webspider.py

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
import urllib.parse
from pathlib import Path
from typing import ClassVar

import w3af.core.data.kb.config as cf
from w3af import ROOT_PATH
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.parsers.utils.form_constants import EXCLUDE
from w3af.core.data.parsers.utils.form_id_matcher_list import FormIDMatcherList
from w3af.plugins.crawl.web_spider import web_spider
from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest

SPIDER_URL = "http://mock/w3af/crawl/web_spider/"
FOLLOW_LINKS_URL = SPIDER_URL + "test_case_01/"
UTF8_URL = "http://mock/core/encoding_utf8/"
EUC_JP_URL = "http://mock/core/encoding_euc-jp/"


def _links(*hrefs):
    anchors = "".join(f'<a href="{href}">{href}</a>' for href in hrefs)
    return f"<html><body>{anchors}</body></html>"


def _page(text):
    return f"<html><body><p>{text}</p></body></html>"


def _spider_config(*options):
    return {"crawl": (PluginConfig("web_spider", *options),)}


BASIC_CONFIG = _spider_config(
    ("only_forward", True, PluginConfig.BOOL),
    ("ignore_regex", ".*logout.php*", PluginConfig.STR),
)


class WebSpiderTest(PluginTest):
    def generic_scan(self, plugins, base_directory, start_url, expected_files):
        self._scan(start_url, plugins)

        # Add the webroot to the list of expected files
        expected_files.append("")
        expected_urls = {
            URL(base_directory).url_join(end).url_string for end in expected_files
        }

        urls = self.kb.get_all_known_urls()
        found_urls = {str(u) for u in urls}

        self.assertEqual(found_urls, expected_urls)


class TestWebSpiderFollowLinks(WebSpiderTest):

    target_url = FOLLOW_LINKS_URL

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(
            FOLLOW_LINKS_URL,
            _links(
                "1.html",
                "logout.php",
                "../outside.html",
                "http://external.example/page.html",
            ),
        ),
        MockResponse(FOLLOW_LINKS_URL + "1.html", _links("2.html")),
        MockResponse(FOLLOW_LINKS_URL + "2.html", _links("3.html")),
        MockResponse(FOLLOW_LINKS_URL + "3.html", _links("4.html", "a b.html")),
        MockResponse(FOLLOW_LINKS_URL + "4.html", _links("d f/index.html")),
        MockResponse(FOLLOW_LINKS_URL + "a%20b.html", _page("a b")),
        MockResponse(FOLLOW_LINKS_URL + "d%20f/", _page("d f directory")),
        MockResponse(FOLLOW_LINKS_URL + "d%20f/index.html", _page("d f index")),
        MockResponse(FOLLOW_LINKS_URL + "logout.php", _page("Bye")),
        MockResponse(SPIDER_URL + "outside.html", _page("Outside")),
    ]

    def test_spider_found_urls(self):
        expected_files = [
            "1.html",
            "2.html",
            "3.html",
            "4.html",
            "d%20f/index.html",
            "a%20b.html",
            "d%20f/",
        ]

        self.generic_scan(
            BASIC_CONFIG, FOLLOW_LINKS_URL, FOLLOW_LINKS_URL, expected_files
        )

        requested = {r.uri for r in self.received_requests}
        self.assertNotIn(FOLLOW_LINKS_URL + "logout.php", requested)
        self.assertNotIn(SPIDER_URL + "outside.html", requested)
        self.assertNotIn("http://external.example/page.html", requested)


UTF8_FILES = ["vúlnerable.py", "é.py", "改.py", "проверка.py"]


def _utf8_file(mock_response, request, uri, response_headers):
    file_name = urllib.parse.unquote(urllib.parse.urlsplit(uri).path).split("/")[-1]
    response_headers["Content-Type"] = "text/html; charset=utf-8"

    if file_name not in UTF8_FILES:
        return 404, response_headers, "Not found"

    return 200, response_headers, _page(f"The {file_name} file")


class TestWebSpiderUTF8(WebSpiderTest):

    target_url = UTF8_URL

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(
            UTF8_URL, _links(*UTF8_FILES), content_type="text/html; charset=utf-8"
        ),
        MockResponse(re.compile(re.escape(UTF8_URL) + r".+\.py"), body=_utf8_file),
    ]

    def test_utf8_urls(self):
        self.generic_scan(BASIC_CONFIG, UTF8_URL, UTF8_URL, list(UTF8_FILES))


class TestWebSpiderEUCJP(WebSpiderTest):

    target_url = EUC_JP_URL

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(
            EUC_JP_URL,
            _links("raw-qs-jp.py", "qs-jp.py?q=日本語").encode("euc-jp"),
            content_type="text/html; charset=euc-jp",
        ),
        MockResponse(
            re.compile(re.escape(EUC_JP_URL) + r"(raw-)?qs-jp\.py.*"),
            _page("日本語").encode("euc-jp"),
            content_type="text/html; charset=euc-jp",
        ),
    ]

    def test_euc_jp_urls(self):
        expected_files = ["raw-qs-jp.py", "qs-jp.py"]

        self.generic_scan(BASIC_CONFIG, EUC_JP_URL, EUC_JP_URL, expected_files)


class TestWebSpiderRelativeURLsWithRegex(WebSpiderTest):

    target_url = SPIDER_URL + "relativeRegex.html"

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(
            target_url,
            "<html><body><script>"
            'var hidden = "/w3af/crawl/web_spider/hidden/secret.html";'
            'var missing = "/w3af/crawl/web_spider/hidden/missing.html";'
            "</script></body></html>",
        ),
        MockResponse(SPIDER_URL + "hidden/secret.html", _page("Secret")),
    ]

    def test_spider_relative_urls_found_with_regex(self):
        self._scan(self.target_url, _spider_config())

        urls = {str(u) for u in self.kb.get_all_known_urls()}
        self.assertIn(SPIDER_URL + "hidden/secret.html", urls)
        self.assertNotIn(SPIDER_URL + "hidden/missing.html", urls)


class TestWebSpiderTraverseDirectories(WebSpiderTest):

    target_url = SPIDER_URL + "a/b/c/d/"

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(target_url, _page("Directory d")),
        MockResponse(SPIDER_URL + "a/b/c/", _page("Directory c")),
        MockResponse(SPIDER_URL + "a/", _page("Directory a")),
    ]

    def test_spider_traverse_directories(self):
        self._scan(self.target_url, _spider_config())

        urls = {str(u) for u in self.kb.get_all_known_urls()}
        expected = {SPIDER_URL + path for path in ("a/b/c/d/", "a/b/c/", "a/")}
        self.assertEqual(urls, expected)


class TestWebSpiderFilters(WebSpiderTest):

    target_url = SPIDER_URL + "filters/"

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(
            target_url,
            _links(
                "manual.PDF",
                "private/index.html",
                "public.html",
                "login.html",
                "logo.png",
                "data.bin",
                "missing/",
                "broken.html",
                "forbidden.html",
            )
            + '<form action="nowhere/" method="POST"><input name="a"/></form>'
            + '<form action="nowhere/" method="POST"><input name="b"/></form>'
            + '<form action="private/" method="POST"><input name="c"/></form>',
        ),
        MockResponse(target_url + "manual.PDF", "%PDF-1.4", "application/pdf"),
        MockResponse(target_url + "private/index.html", _page("Private")),
        MockResponse(target_url + "public.html", _page("Public")),
        MockResponse(target_url + "login.html", "Login required", status=401),
        MockResponse(target_url + "logo.png", b"\x89PNG\r\n", "image/png"),
        MockResponse(
            target_url + "data.bin", b"\x00\x01\x02binary", "application/octet-stream"
        ),
        MockResponse(
            target_url + "missing/",
            _links("../found-from-404.html", "again/"),
            status=404,
        ),
        MockResponse(target_url + "found-from-404.html", _page("Found from 404")),
        MockResponse(target_url + "forbidden.html", "Forbidden", status=403),
    ]

    def test_filters_and_special_responses(self):
        plugins = _spider_config(
            ("follow_regex", ".*/filters/(?!private).*", PluginConfig.STR),
            ("ignore_extensions", "pdf", PluginConfig.LIST),
        )
        self._scan(self.target_url, plugins)

        urls = {str(u) for u in self.kb.get_all_known_urls()}
        self.assertIn(self.target_url + "public.html", urls)
        self.assertIn(self.target_url + "found-from-404.html", urls)
        self.assertIn(self.target_url + "login.html", urls)
        self.assertIn(self.target_url + "logo.png", urls)
        self.assertIn(self.target_url + "data.bin", urls)
        self.assertNotIn(self.target_url + "manual.PDF", urls)
        self.assertNotIn(self.target_url + "private/index.html", urls)
        self.assertNotIn(self.target_url + "missing/", urls)
        self.assertNotIn(self.target_url + "broken.html", urls)

        posts = [r for r in self.received_requests if r.command == "POST"]
        self.assertTrue(posts)


class TestWebSpiderWithoutTargets:
    def test_end_without_core_is_safe(self):
        spider = web_spider()
        spider.end()

    def test_first_run_without_targets(self):
        previous = cf.cf.get("targets")
        cf.cf.save("targets", [])
        try:
            spider = web_spider()
            spider._handle_first_run()
        finally:
            cf.cf.save("targets", previous)

        if spider._target_urls != []:
            raise AssertionError
        if spider._target_domain is not None:
            raise AssertionError

    def test_long_desc(self):
        if "only_forward" not in web_spider().get_long_desc():
            raise AssertionError


class TestRelativePathsIn404(PluginTest):
    """
    This test reproduces the issue #5834 which generates an endless crawl loop

    :see: https://github.com/andresriancho/w3af/issues/5834
    """

    target_url = "http://mock/"

    _run_configs: ClassVar[dict] = {
        "cfg": {
            "target": target_url,
            "plugins": {"crawl": (PluginConfig("web_spider"),)},
        }
    }

    TEST_ROOT = os.path.join(
        ROOT_PATH, "plugins", "tests", "crawl", "web_spider", "5834"
    )

    GALERIA_HTML = Path(os.path.join(TEST_ROOT, "galeria-root.html")).read_text()
    INDEX_HTML = Path(os.path.join(TEST_ROOT, "index.html")).read_text()

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(re.compile("http://mock/galeria/.*"), GALERIA_HTML),
        MockResponse("http://mock/", "Thanks.", method="POST"),
        MockResponse("http://mock/", INDEX_HTML),
    ]

    def test_crawl_404_relative(self):
        cfg = self._run_configs["cfg"]
        self._scan(cfg["target"], cfg["plugins"])

        # Define the expected/desired output
        expected_files = ["", "/galeria/", "/i18n/setlang/", "/reserva/resumen/"]
        expected_urls = {
            URL(self.target_url).url_join(end).url_string for end in expected_files
        }

        # Pylint fails to detect the object types that come out of the KB
        urls = self.kb.get_all_known_urls()
        found_urls = {str(u) for u in urls}

        self.assertEqual(found_urls, expected_urls)


class TestDeadLock(PluginTest):
    """
    This test reproduces a lock that I've found while debugging #5834, as far as
    I know, it has nothing to do with #5834 itself.

    I tried, but was unable to make this test fail when the dead-lock is found,
    instead when the dead-lock is found the test will "hang", CI will timeout,
    and in your workstation you'll have to manually kill it.
    """

    target_url = "http://mock/"

    _run_configs: ClassVar[dict] = {
        "cfg": {
            "target": target_url,
            "plugins": {"crawl": (PluginConfig("web_spider"),)},
        }
    }

    TEST_ROOT = os.path.join(
        ROOT_PATH, "plugins", "tests", "crawl", "web_spider", "5834"
    )

    INDEX_HTML = Path(os.path.join(TEST_ROOT, "index.html")).read_text()

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse("http://mock/", INDEX_HTML),
        MockResponse("http://mock/", "Thanks.", method="POST"),
    ]

    def test_no_lock(self):
        cfg = self._run_configs["cfg"]
        self._scan(cfg["target"], cfg["plugins"])


class TestFormExclusions(PluginTest):
    """
    This is an integration test for form exclusions

    :see: https://github.com/andresriancho/w3af/issues/15161
    """

    target_url = "http://mock/"

    scan_config: ClassVar[dict] = {
        "target": target_url,
        "plugins": {"crawl": (PluginConfig("web_spider"),)},
    }

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(
            "http://mock/",
            "<html>"
            ""
            '<form action="/out/" method="POST">'
            '<input name="x" /></form>'
            ""
            '<form action="/in/" method="POST">'
            '<input name="x" /></form>'
            ""
            "</html>",
        ),
        MockResponse("http://mock/out/", "Thanks.", method="POST"),
        MockResponse("http://mock/in/", "Thanks.", method="POST"),
    ]

    def test_form_exclusions(self):
        user_value = '[{"action": "/out.*"}]'
        cf.cf.save("form_id_list", FormIDMatcherList(user_value))
        cf.cf.save("form_id_action", EXCLUDE)

        self._scan(self.scan_config["target"], self.scan_config["plugins"])

        # Define the expected/desired output
        expected_files = ["", "/in/"]
        expected_urls = {
            URL(self.target_url).url_join(end).url_string for end in expected_files
        }

        # Pylint fails to detect the object types that come out of the KB
        urls = self.kb.get_all_known_urls()
        found_urls = {str(u) for u in urls}

        self.assertEqual(found_urls, expected_urls)

        # revert any changes to the default so we don't affect other tests
        cf.cf.save("form_id_list", FormIDMatcherList("[]"))
        cf.cf.save("form_id_action", EXCLUDE)
