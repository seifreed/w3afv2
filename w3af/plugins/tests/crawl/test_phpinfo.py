"""
test_phpinfo.py

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
import unittest
from pathlib import Path
from typing import ClassVar, cast

import w3af.core.controllers.output_manager as om
from w3af import ROOT_PATH
from w3af.core.data.dc.headers import Headers
from w3af.core.data.kb.config import Config
from w3af.core.data.kb.knowledge_base import DBKnowledgeBase
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.url.http_response import HTTPResponse
from w3af.plugins.crawl.phpinfo import (
    ANALYSIS_FUNCTIONS,
    PHP_INFO_FILES,
    PHP_INFO_FILES_LOWERCASE,
    phpinfo,
)
from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest

TARGET_URL = "http://httpretty/"
PHPINFO_DIR = os.path.join(ROOT_PATH, "plugins", "tests", "crawl", "phpinfo")

RUN_CONFIG: dict = {"crawl": (PluginConfig("phpinfo"),)}


def phpinfo_site(phpinfo_file):
    body = Path(os.path.join(PHPINFO_DIR, phpinfo_file)).read_text()
    return [
        MockResponse(TARGET_URL, body="index home page"),
        MockResponse(TARGET_URL + "phpversion.php", body=body),
        MockResponse(TARGET_URL + "info.php", body="Not a phpinfo page"),
        MockResponse(
            TARGET_URL + "x.php",
            body='alt="PHP Logo" /></a><h1 class="p">PHP Version 5.1.6</h1>',
        ),
    ]


class PHPInfoScanMixin:

    target_url: str | None = TARGET_URL
    EXPECTED_INFOS: ClassVar[set[str]] = set()

    def test_phpinfo(self):
        test_case = cast(PluginTest, self)
        target_url = self.target_url
        if target_url is None:
            raise AssertionError("phpinfo test requires a target URL")

        test_case._scan(target_url, RUN_CONFIG)

        urls = [url.url_string for url in test_case.kb.get_all_known_urls()]
        test_case.assertIn(target_url + "phpversion.php", urls)
        test_case.assertNotIn(target_url + "info.php", urls)
        test_case.assertNotIn(target_url + "x.php", urls)

        infos = test_case.kb.get("phpinfo", "phpinfo")

        info_urls = {i.get_url().url_string for i in infos}
        test_case.assertEqual(info_urls, {target_url + "phpversion.php"})

        found_infos = {i.get_name() for i in infos}
        test_case.assertEqual(found_infos, self.EXPECTED_INFOS)


class TestPHPInfo516(PHPInfoScanMixin, PluginTest):

    MOCK_RESPONSES: ClassVar[list] = phpinfo_site("phpinfo-5.1.6.html")

    EXPECTED_INFOS: ClassVar[set] = {
        "phpinfo() file found",
        "PHP register_globals: On",
        "PHP allow_url_fopen: On",
        "PHP expose_php: On",
        "PHP running with privileged user",
        "PHP disable_functions weakness",
        "PHP enable_dl: On",
        "PHP high memory limit",
        "PHP file_uploads: On",
        "PHP magic_quotes_gpc: Off",
        "PHP open_basedir:disabled",
        "PHP session.hash_function:md5",
        "PHP upload_tmp_dir is world readable",
    }


class TestPHPInfo4311(PHPInfoScanMixin, PluginTest):

    MOCK_RESPONSES: ClassVar[list] = phpinfo_site("phpinfo-4.3.11.html")

    EXPECTED_INFOS: ClassVar[set] = {
        "phpinfo() file found",
        "PHP register_globals: Off",
        "PHP disable_functions weakness",
        "PHP curl_file_support:not_fixed",
        "PHP enable_dl: On",
        "PHP high memory limit",
        "PHP high POST max size",
        "PHP upload_max_filesize:high",
        "PHP file_uploads: On",
        "PHP magic_quotes_gpc: On",
        "PHP open_basedir:disabled",
    }


class TestPHPInfo513rc4dev(PHPInfoScanMixin, PluginTest):

    MOCK_RESPONSES: ClassVar[list] = phpinfo_site("phpinfo-5.1.3-rc4dev.html")

    EXPECTED_INFOS: ClassVar[set] = {
        "phpinfo() file found",
        "PHP register_globals: Off",
        "PHP allow_url_fopen: On",
        "PHP display_errors: On",
        "PHP expose_php: On",
        "PHP disable_functions weakness",
        "PHP curl_file_support:not_fixed",
        "PHP enable_dl: On",
        "PHP high memory limit",
        "PHP upload_tmp_dir is world readable",
        "PHP file_uploads: On",
        "PHP magic_quotes_gpc: On",
        "PHP open_basedir:disabled",
        "PHP session.hash_function:md5",
    }


class TestPHPInfo433(PHPInfoScanMixin, PluginTest):

    MOCK_RESPONSES: ClassVar[list] = phpinfo_site("phpinfo-4.3.3.html")

    EXPECTED_INFOS: ClassVar[set] = {
        "phpinfo() file found",
        "PHP register_globals: On",
        "PHP allow_url_fopen: On",
        "PHP display_errors: On",
        "PHP expose_php: On",
        "PHP running as low privileged user",
        "PHP disable_functions weakness",
        "PHP curl_file_support:not_fixed",
        "PHP enable_dl: On",
        "PHP high POST max size",
        "PHP upload_tmp_dir is world readable",
        "PHP file_uploads: On",
        "PHP magic_quotes_gpc: On",
        "PHP open_basedir:disabled",
    }


class TestPHPInfoFilenames(unittest.TestCase):

    def setUp(self):
        kb.cleanup()
        self.addCleanup(kb.cleanup)
        self.addCleanup(cf.save, "target_os", cf.get("target_os"))

    def test_windows_fingerprint_uses_lowercase_names(self):
        kb.raw_write("fingerprint_os", "operating_system_str", "Windows")

        plugin = phpinfo()
        plugin.set_knowledge_base(kb)
        plugin.set_configuration(cf)
        self.assertEqual(plugin._get_potential_phpinfos(), PHP_INFO_FILES_LOWERCASE)

    def test_target_os_setting_is_used_without_fingerprint(self):
        cf.save("target_os", "unix")

        plugin = phpinfo()
        plugin.set_knowledge_base(kb)
        plugin.set_configuration(cf)
        self.assertEqual(plugin._get_potential_phpinfos(), PHP_INFO_FILES)

    def test_long_desc(self):
        self.assertIn("PHP Info", phpinfo().get_long_desc())


class TestPHPInfoAnalysis(unittest.TestCase):
    """
    Run every analysis function against minimal phpinfo() table rows.
    """

    def setUp(self):
        kb.cleanup()
        self.addCleanup(kb.cleanup)

    def findings(self, *rows):
        url = URL(TARGET_URL + "phpinfo.php")
        body = "".join(rows)
        headers = Headers([("Content-Type", "text/html")])
        response = HTTPResponse(200, body, headers, url, url, _id=1)

        for analysis_function in ANALYSIS_FUNCTIONS:
            analysis_function(response, kb, om.out)

        return {i.get_name() for i in kb.get("phpinfo", "phpinfo")}

    def test_empty_page(self):
        self.assertEqual(self.findings("nothing here"), set())

    def test_enabled_settings(self):
        rows = (
            '<tr><td class="e">register_globals</td><td class="v">On</td></tr>',
            '<tr><td class="e">allow_url_include</td><td class="v">On</td></tr>',
            '<tr><td class="e">display_errors</td><td class="v">On</td></tr>',
            '<tr><td class="e">User/Group </td><td class="v">www(1000)/1000</td></tr>',
            '<tr><td class="e">cgi_force_redirect</td><td class="v">Off</td></tr>',
            '<tr><td class="e">session.save_path</td><td class="v"><i>no value</i></td>',
            '<tr><td class="e">session.use_trans</td><td class="v">On</td></tr>',
            '<tr><td class="e">session.cookie_httponly</td><td class="v">Off</td>',
            '<tr><td class="e">default_charset</td><td class="v">Off</td></tr>',
            '<tr><td class="e">enable_dl</td><td class="v">Off</td></tr>',
            '<tr><td class="e">post_max_size</td><td class="v">100M</td></tr>',
            '<tr><td class="e">upload_max_filesize</td><td class="v">100M</td></tr>',
            '<tr><td class="e">magic_quotes_gpc</td><td class="v">On</td></tr>',
            '<tr><td class="e">open_basedir</td><td class="v">/var/www</td></tr>',
            '<tr><td class="e">session.hash_function</td><td class="v">1</td></tr>',
            '<h1 class="p">PHP Version 5.1.2</h1>',
        )

        self.assertEqual(
            self.findings(*rows),
            {
                "PHP register_globals: On",
                "PHP allow_url_include: On",
                "PHP display_errors: On",
                "PHP running as low privileged user",
                "PHP cgi_force_redirect: Off",
                "Word readable PHP session_save_path",
                "PHP session_use_trans: On",
                "PHP session.cookie_httponly: Off",
                "PHP default_charset: Off",
                "PHP enable_dl: Off",
                "PHP high POST max size",
                "PHP upload_max_filesize:high",
                "PHP magic_quotes_gpc: On",
                "PHP open_basedir:enabled",
                "PHP session.hash_function:sha",
                "PHP curl_file_support:not_fixed",
            },
        )

    def test_secure_settings(self):
        functions = ",".join(f"func{i}" for i in range(8))
        rows = (
            '<tr><td class="e">register_globals</td><td class="v">Off</td></tr>',
            f'<tr><td class="e">disable_functions</td><td class="v">{functions}</td>',
            '<tr><td class="e">cgi_force_redirect</td><td class="v">On</td></tr>',
            '<tr><td class="e">memory_limit</td><td class="v">8M</td></tr>',
            '<tr><td class="e">post_max_size</td><td class="v">8M</td></tr>',
            '<tr><td class="e">upload_max_filesize</td><td class="v">2M</td></tr>',
            '<h1 class="p">PHP Version 5.2.0</h1>',
        )

        self.assertEqual(self.findings(*rows), {"PHP register_globals: Off"})

    def test_curl_file_support_by_version(self):
        expected = {
            "4.3.11": {"PHP curl_file_support:not_fixed"},
            "4.4.5": set(),
            "5.1.6": set(),
            "6.0.0": set(),
            "3.0.0": set(),
        }

        for version, findings in expected.items():
            kb.cleanup()
            row = f'<h1 class="p">PHP Version {version}</h1>'
            self.assertEqual(self.findings(row), findings, version)


cf = Config()


kb = DBKnowledgeBase()
