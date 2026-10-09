"""
test_import_results.py

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

import base64
import os
import re
import tempfile
import unittest
from typing import ClassVar

from w3af import ROOT_PATH
from w3af.core.data.dc.multipart_container import MultipartContainer
from w3af.plugins.crawl.import_results import import_results
from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest


class TestImportResults(PluginTest):

    base_url = "http://127.0.0.1:8000/"
    target_url = base_url

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(re.compile(r"http://127\.0\.0\.1:8000/.*"), "imported site")
    ]

    BASE_PATH = os.path.join(ROOT_PATH, "plugins", "tests", "crawl", "import_results")

    input_base64 = os.path.join(BASE_PATH, "w3af.base64")
    input_burp = os.path.join(BASE_PATH, "burp-no-base64.xml")
    input_burp_b64 = os.path.join(BASE_PATH, "burp-base64.xml")

    _run_configs: ClassVar[dict] = {
        "w3af": {
            "target": base_url,
            "plugins": {
                "crawl": (
                    PluginConfig(
                        "import_results",
                        ("input_base64", input_base64, PluginConfig.STR),
                        ("input_burp", "", PluginConfig.STR),
                    ),
                )
            },
        },
        "burp64": {
            "target": base_url,
            "plugins": {
                "crawl": (
                    PluginConfig(
                        "import_results",
                        ("input_base64", "", PluginConfig.STR),
                        ("input_burp", input_burp_b64, PluginConfig.STR),
                    ),
                )
            },
        },
        "burp": {
            "target": base_url,
            "plugins": {
                "crawl": (
                    PluginConfig(
                        "import_results",
                        ("input_base64", "", PluginConfig.STR),
                        ("input_burp", input_burp, PluginConfig.STR),
                    ),
                )
            },
        },
    }

    def test_base64(self):
        cfg = self._run_configs["w3af"]
        self._scan(cfg["target"], cfg["plugins"])

        fuzzable_requests = self.kb.get_all_known_fuzzable_requests()

        #
        #   Assert that headers are loaded from the file
        #
        mozilla = 0
        for fuzzable_request in fuzzable_requests:
            user_agent, _ = fuzzable_request.get_headers().iget("user-agent")

            if user_agent is None:
                continue

            self.assertIn("mozilla", user_agent.lower())
            mozilla += 1

        self.assertGreater(mozilla, 0)

        #
        #   Assert that POST requests and their data are loaded from file
        #
        post_frs = [fr for fr in fuzzable_requests if fr.get_method() == "POST"]
        self.assertEqual(len(post_frs), 1)

        post_fr = post_frs[0]
        expected_post_url = "http://127.0.0.1:8000/core/file_upload/upload.py"

        file_contents = "Hello\nworld\n\nABC\n"

        self.assertEqual(post_fr.get_url().url_string, expected_post_url)
        self.assertEqual(post_fr.get_raw_data()["_file"][0], file_contents)

        #
        #   Assert that we found the URLs
        #
        urls = [fr.get_uri().url_string for fr in fuzzable_requests]

        expected_urls = {
            "http://127.0.0.1:8000/",
            "http://127.0.0.1:8000/static/moth/css/sticky-footer-navbar.css",
            "http://127.0.0.1:8000/core/file_upload/upload.py",
            "http://127.0.0.1:8000/static/moth/js/bootstrap.min.js",
            "http://127.0.0.1:8000/static/moth/css/font-awesome/css/font-awesome.min.css",
            "http://127.0.0.1:8000/static/moth/js/jquery.js",
            "http://127.0.0.1:8000/static/moth/css/style.css",
            "http://127.0.0.1:8000/about/",
            "http://127.0.0.1:8000/static/moth/css/bootstrap.min.css",
            "http://127.0.0.1:8000/w3af/file_upload/",
            "http://127.0.0.1:8000/static/moth/images/w3af.png",
        }

        self.assertEqual(set(urls), expected_urls)

    def test_burp_b64(self):
        cfg = self._run_configs["burp64"]
        self._scan(cfg["target"], cfg["plugins"])

        fuzzable_requests = self.kb.get_all_known_fuzzable_requests()

        #
        #   Assert that headers are loaded from the file
        #
        mozilla = 0
        for fuzzable_request in fuzzable_requests:
            user_agent, _ = fuzzable_request.get_headers().iget("user-agent")

            if user_agent is None:
                continue

            self.assertIn("mozilla", user_agent.lower())
            mozilla += 1

        self.assertGreater(mozilla, 0)

        #
        #   Assert that POST requests and their data are loaded from file
        #
        post_frs = [fr for fr in fuzzable_requests if fr.get_method() == "POST"]

        expected_post_urls = {
            "http://127.0.0.1:8000/audit/xss/simple_xss_form.py",
            "http://127.0.0.1:8000/core/file_upload/upload.py",
        }
        post_urls = {fr.get_uri().url_string for fr in post_frs}

        self.assertEqual(expected_post_urls, post_urls)

        expected_post_url = "http://127.0.0.1:8000/core/file_upload/upload.py"
        file_contents = "hello\nworld\n"

        post_fr = None

        for fr in fuzzable_requests:
            if fr.get_url().url_string.endswith("upload.py") and isinstance(
                fr.get_raw_data(), MultipartContainer
            ):
                post_fr = fr
                break

        self.assertEqual(post_fr.get_url().url_string, expected_post_url)
        self.assertIn("_file", post_fr.get_raw_data())
        self.assertEqual(post_fr.get_raw_data()["_file"][0], file_contents)

        #
        #   Assert that we found the URLs
        #
        urls = [fr.get_uri().url_string for fr in fuzzable_requests]

        expected_urls = {
            "http://127.0.0.1:8000/",
            "http://127.0.0.1:8000/core/",
            "http://127.0.0.1:8000/favicon.ico",
            "http://127.0.0.1:8000/audit/xss/simple_xss_form.py",
            "http://127.0.0.1:8000/core/file_upload/upload.py",
            "http://127.0.0.1:8000/audit/",
            "http://127.0.0.1:8000/static/moth/css/font-awesome/fonts/fontawesome-webfont.woff?v=4.0.3",
        }

        self.assertEqual(set(urls), expected_urls)

    def test_burp(self):
        cfg = self._run_configs["burp"]
        self._scan(cfg["target"], cfg["plugins"])

        fuzzable_requests = self.kb.get_all_known_fuzzable_requests()

        #
        #   Assert that headers are loaded from the file
        #
        mozilla = 0
        for fuzzable_request in fuzzable_requests:
            user_agent, _ = fuzzable_request.get_headers().iget("user-agent")

            if user_agent is None:
                continue

            self.assertIn("mozilla", user_agent.lower())
            mozilla += 1

        self.assertGreater(mozilla, 0)

        #
        #   Assert that POST requests and their data are loaded from file
        #
        post_frs = [fr for fr in fuzzable_requests if fr.get_method() == "POST"]

        expected_post_urls = {
            "http://127.0.0.1:8000/audit/xss/simple_xss_form.py",
            "http://127.0.0.1:8000/core/file_upload/upload.py",
        }
        post_urls = {fr.get_uri().url_string for fr in post_frs}

        self.assertEqual(expected_post_urls, post_urls)

        post_fr = None

        for fr in fuzzable_requests:
            if fr.get_url().url_string.endswith("upload.py") and isinstance(
                fr.get_raw_data(), MultipartContainer
            ):
                post_fr = fr
                break

        expected_post_url = "http://127.0.0.1:8000/core/file_upload/upload.py"
        file_contents = "hello\nworld\n"

        self.assertEqual(post_fr.get_url().url_string, expected_post_url)
        self.assertEqual(post_fr.get_raw_data()["_file"][0], file_contents)

        #
        #   Assert that we found the URLs
        #
        urls = [fr.get_uri().url_string for fr in fuzzable_requests]

        expected_urls = {
            "http://127.0.0.1:8000/",
            "http://127.0.0.1:8000/core/",
            "http://127.0.0.1:8000/favicon.ico",
            "http://127.0.0.1:8000/audit/xss/simple_xss_form.py",
            "http://127.0.0.1:8000/core/file_upload/upload.py",
            "http://127.0.0.1:8000/audit/",
            "http://127.0.0.1:8000/static/moth/css/font-awesome/fonts/fontawesome-webfont.woff?v=4.0.3",
        }

        self.assertEqual(set(urls), expected_urls)


def b64_line(raw_request):
    return base64.b64encode(raw_request.encode("utf-8")) + b"\n"


class TestImportResultsInputs(unittest.TestCase):

    def setUp(self):
        self.plugin = import_results()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

    def write_input(self, name, content):
        path = os.path.join(self.temp_dir.name, name)
        with open(path, "wb") as input_fh:
            input_fh.write(content)
        return path

    def configure(self, input_base64="", input_burp=""):
        options = self.plugin.get_options()
        options["input_base64"].set_value(input_base64)
        options["input_burp"].set_value(input_burp)
        self.plugin.set_options(options)

    def imported_urls(self):
        self.plugin._load_data_from_base64()
        self.plugin._load_data_from_burp()

        urls = []
        while not self.plugin.output_queue.empty():
            urls.append(self.plugin.output_queue.get().get_uri().url_string)
        return urls

    def test_no_input_files(self):
        self.configure()

        self.assertEqual(self.imported_urls(), [])

    def test_base64_skips_comments_blank_and_invalid_lines(self):
        content = (
            b"# exported by w3af\n"
            b"\n"
            b"not base64 at all!\n"
            + b64_line("NOT A REQUEST\r\n\r\n")
            + b64_line("GET http://127.0.0.1:8000/ok HTTP/1.1\r\n\r\n")
        )
        self.configure(input_base64=self.write_input("input.b64", content))

        self.assertEqual(self.imported_urls(), ["http://127.0.0.1:8000/ok"])

    def test_input_files_removed_after_configuration(self):
        input_base64 = self.write_input("input.b64", b"")
        input_burp = self.write_input("burp.xml", b"<items/>")
        self.configure(input_base64=input_base64, input_burp=input_burp)

        os.remove(input_base64)
        os.remove(input_burp)

        self.assertEqual(self.imported_urls(), [])

    def test_burp_invalid_xml(self):
        burp = self.write_input("burp.xml", b"<items><item>")
        self.configure(input_burp=burp)

        self.assertEqual(self.imported_urls(), [])

    def test_burp_invalid_request(self):
        burp = self.write_input(
            "burp.xml", b"<items><request>INVALID\n\n</request></items>"
        )
        self.configure(input_burp=burp)

        self.assertEqual(self.imported_urls(), [])

    def test_burp_request_without_base64_attribute(self):
        burp = self.write_input(
            "burp.xml",
            b"<items><item><url>ignored</url>"
            b"<request>GET /plain HTTP/1.1\nHost: 127.0.0.1:8000\n\n</request>"
            b"</item></items>",
        )
        self.configure(input_burp=burp)

        self.assertEqual(self.imported_urls(), ["http://127.0.0.1:8000/plain"])

    def test_long_desc(self):
        self.assertIn("input_burp", self.plugin.get_long_desc())
