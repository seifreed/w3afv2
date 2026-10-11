"""
test_retirejs.py

Copyright 2018 Andres Riancho

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

The retire.js CLI is replaced by retirejs/retire_standin.py, a small real
program speaking the same command line and JSON output format, and the
vulnerability database is served from a local HTTP server.
"""

import json
import os
import shutil
import stat
import sys
import tempfile
from pathlib import Path

from w3af import ROOT_PATH
from w3af.core.data.constants import severity
from w3af.core.data.kb.knowledge_base import DBKnowledgeBase
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.url.extended_urllib import ExtendedUrllib
from w3af.plugins.grep.retirejs import retirejs
from w3af.plugins.tests.canned_http_server import CannedHTTPServer, CannedReply
from w3af.plugins.tests.grep.grep_test_utils import (
    GrepPluginTestCase,
    make_request,
    make_response,
)
from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest

FIXTURES = Path(ROOT_PATH) / "plugins" / "tests" / "grep" / "retirejs"
JQUERY_VULN = (FIXTURES / "jquery.js").read_text()
JS_REPOSITORY = (FIXTURES / "jsrepository.json").read_text()
OLDLIB = "/* oldlib v1.0.0 */\nvar oldlib = {};"
CLEAN_JS = "var clean = true;"
JS = "application/javascript"


def write_retire_standin(directory, **behavior):
    """
    :return: The path to an executable retire.js stand-in which behaves as
             configured by the keyword arguments (see DEFAULT_BEHAVIOR).
    """
    path = Path(directory) / "retire"
    source = (FIXTURES / "retire_standin.py").read_text()
    path.write_text(f"#!{sys.executable}\nBEHAVIOR = {behavior!r}\n{source}")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return str(path)


EXPECTED_VULN_DESC = """\
A JavaScript library with known vulnerabilities was identified at http://httpretty/js/jquery.js. The library was identified as "jquery" version 1.11.0 and has these known vulnerabilities:

 - 3rd party CORS request may execute
 - parseHTML() executes scripts in event handlers
 - jQuery before 3.4.0, as used in Drupal, Backdrop CMS, and other products, mishandles jQuery.extend(true, {}, ...) because of Object.prototype pollution

Consider updating to the latest stable release of the affected library."""


class RetireJSScanTest(PluginTest):

    target_url = "http://httpretty"

    INDEX = '<html><script src="/js/jquery.js"></script></html>'

    JQUERY_CONTENT_TYPE = JS

    def setUp(self):
        self.standin_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.standin_dir)
        self.MOCK_RESPONSES = [
            MockResponse("http://httpretty/", body=self.INDEX),
            MockResponse(
                "http://httpretty/jsrepository.json",
                body=JS_REPOSITORY,
                content_type="application/json",
            ),
            MockResponse(
                "http://httpretty/js/jquery.js",
                body=JQUERY_VULN,
                content_type=self.JQUERY_CONTENT_TYPE,
            ),
        ]
        super().setUp()

    def scan_with_standin(self):
        plugins = {
            "grep": (
                PluginConfig(
                    "retirejs",
                    (
                        "retire_path",
                        write_retire_standin(self.standin_dir),
                        PluginConfig.STR,
                    ),
                    (
                        "retire_db_url",
                        "http://httpretty/jsrepository.json",
                        PluginConfig.URL,
                    ),
                ),
            ),
            "crawl": (
                PluginConfig("web_spider", ("only_forward", True, PluginConfig.BOOL)),
            ),
        }
        self._scan(self.target_url, plugins)
        return self.kb.get("retirejs", "js")


class TestRetireJSNotAnalyzeHTMLContentType(RetireJSScanTest):

    JQUERY_CONTENT_TYPE = "text/html"

    def test_is_vulnerable_not_detected(self):
        vulns = self.scan_with_standin()
        self.assertEqual(len(vulns), 0, vulns)


class TestRetireJS(RetireJSScanTest):

    def test_is_vulnerable_detected(self):
        vulns = self.scan_with_standin()

        self.assertEqual(len(vulns), 1, vulns)

        vuln = vulns[0]

        self.assertEqual(vuln.get_name(), "Vulnerable JavaScript library in use")
        self.assertEqual(vuln.get_url().url_string, "http://httpretty/js/jquery.js")
        self.assertEqual(vuln.get_desc(with_id=False), EXPECTED_VULN_DESC)
        self.assertEqual(vuln.get_severity(), severity.LOW)


def _serve_repository(request):
    if request.path == "/jsrepository.json":
        return CannedReply(200, {"Content-Type": "application/json"}, JS_REPOSITORY)
    return CannedReply(404, {"Content-Type": "text/html"}, "Not found")


class RetireJSUnitTest(GrepPluginTestCase):

    def setUp(self):
        super().setUp()

        self.standin_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.standin_dir)

        self.server = CannedHTTPServer(_serve_repository)
        self.server.start()
        self.addCleanup(self.server.stop)

        self.uri_opener = ExtendedUrllib()
        self.addCleanup(self.uri_opener.end)

    def server_url(self, path):
        return f"http://127.0.0.1:{self.server.port}{path}"

    def make_plugin(self, retire_path=None, db_path="/jsrepository.json", **behavior):
        plugin = retirejs()
        options = plugin.get_options()
        options["retire_path"].set_value(
            retire_path or write_retire_standin(self.standin_dir, **behavior)
        )
        options["retire_db_url"].set_value(self.server_url(db_path))
        plugin.set_options(options)
        plugin.set_url_opener(self.uri_opener)
        return plugin

    def send_js(self, plugin, body, path="/js/lib.js", content_type=JS, **kwargs):
        method = kwargs.pop("method", "GET")
        url = f"http://www.w3af.com{path}"
        response = make_response(
            url=url, body=body, content_type=content_type, **kwargs
        )
        plugin.grep(make_request(url=url, method=method), response)

    def vulns(self):
        return kb.get("retirejs", "js")


class TestRetireJSInstallationChecks(RetireJSUnitTest):

    def test_valid_standin_passes_both_checks(self):
        plugin = self.make_plugin()
        self.assertTrue(plugin._get_is_valid_retire_version())
        self.assertTrue(plugin._retire_smoke_test())

    def test_missing_executable_disables_plugin(self):
        plugin = self.make_plugin(retire_path=os.path.join(self.standin_dir, "nope"))

        self.send_js(plugin, JQUERY_VULN)
        plugin.end()

        self.assertFalse(plugin._is_valid_retire_version)
        self.assertFalse(plugin._is_valid_retirejs_exit_code)
        self.assertEqual(plugin._batch, [])
        self.assertIsNone(plugin._retire_db_filename)

    def test_unsupported_version(self):
        plugin = self.make_plugin(version="1.6.0")
        self.assertFalse(plugin._get_is_valid_retire_version())

    def test_version_command_failure(self):
        plugin = self.make_plugin(version_exit=1)
        self.assertFalse(plugin._get_is_valid_retire_version())

    def test_smoke_test_failure(self):
        plugin = self.make_plugin(scan_exit=1)
        self.assertFalse(plugin._retire_smoke_test())

    def test_options(self):
        plugin = self.make_plugin(retire_path="/opt/retire/bin/retire")
        options = plugin.get_options()

        self.assertEqual(options["retire_path"].get_value(), "/opt/retire/bin/retire")
        self.assertEqual(
            options["retire_db_url"].get_value(),
            URL(self.server_url("/jsrepository.json")),
        )
        self.assertIn("retirejs", plugin.get_long_desc())


class TestRetireJSResponseFilters(RetireJSUnitTest):

    def test_ignored_responses_are_not_batched(self):
        plugin = self.make_plugin()

        self.send_js(plugin, JQUERY_VULN, method="POST")
        self.send_js(plugin, JQUERY_VULN, code=404)
        self.send_js(plugin, JQUERY_VULN, content_type="text/html")

        self.assertEqual(plugin._batch, [])
        self.assertIsNone(plugin._retire_db_filename)

    def test_same_url_and_same_content_are_analyzed_once(self):
        plugin = self.make_plugin()

        self.send_js(plugin, JQUERY_VULN, path="/a.js")
        self.send_js(plugin, CLEAN_JS, path="/a.js")
        self.send_js(plugin, JQUERY_VULN, path="/b.js")

        self.assertEqual(len(plugin._batch), 1)
        plugin.end()
        self.assertEqual(len(self.vulns()), 1)

    def test_database_download_failure(self):
        plugin = self.make_plugin(db_path="/missing.json")

        self.send_js(plugin, JQUERY_VULN)

        self.assertIsNone(plugin._retire_db_filename)
        self.assertEqual(plugin._batch, [])


class TestRetireJSBatches(RetireJSUnitTest):

    def test_full_batch_is_analyzed_during_grep(self):
        plugin = self.make_plugin()
        plugin.BATCH_SIZE = 2

        self.send_js(plugin, JQUERY_VULN, path="/jquery.js")
        self.send_js(plugin, OLDLIB, path="/oldlib.js")

        self.assertEqual(plugin._batch, [])
        self.assertEqual(os.listdir(plugin._get_js_temp_directory()), [])

        by_url = {v.get_url().get_file_name(): v for v in self.vulns()}
        self.assertEqual(set(by_url), {"jquery.js", "oldlib.js"})
        self.assertEqual(by_url["jquery.js"].get_severity(), severity.LOW)
        self.assertEqual(by_url["oldlib.js"].get_severity(), severity.MEDIUM)

    def test_end_without_pending_batch(self):
        plugin = self.make_plugin()
        plugin.end()
        self.assertEqual(self.vulns(), [])

    def test_clean_javascript(self):
        plugin = self.make_plugin()

        self.send_js(plugin, CLEAN_JS)
        plugin.end()

        self.assertEqual(self.vulns(), [])
        self.assertEqual(plugin._batch, [])


class TestRetireJSOutputHandling(RetireJSUnitTest):

    def run_batch(self, timeout=None, **behavior):
        """
        Pass the installation checks with a working stand-in, then analyze the
        batch with one that misbehaves as configured.
        """
        plugin = self.make_plugin()
        self.send_js(plugin, JQUERY_VULN)
        self.assertEqual(len(plugin._batch), 1)

        plugin._retire_path = write_retire_standin(self.standin_dir, **behavior)
        if timeout is not None:
            plugin.RETIRE_TIMEOUT = timeout
        plugin.end()

        self.assertEqual(plugin._batch, [])
        return self.vulns()

    def run_with_output(self, report):
        return self.run_batch(scan_exit=13, raw_output=json.dumps(report))

    def test_timeout(self):
        self.assertEqual(self.run_batch(timeout=0.5, sleep=5), [])

    def test_valid_output(self):
        self.assertEqual(len(self.run_batch()), 1)

    def test_missing_output_file(self):
        self.assertEqual(self.run_batch(delete_output=True), [])

    def test_invalid_json_output(self):
        self.assertEqual(self.run_batch(scan_exit=13, raw_output="not json"), [])

    def test_finding_for_unknown_file(self):
        result = {
            "component": "jquery",
            "version": "1.11.0",
            "vulnerabilities": [{"severity": "low", "identifiers": {"summary": "x"}}],
        }
        report = {"data": [{"file": "/elsewhere/lib.js", "results": [result]}]}
        self.assertEqual(self.run_with_output(report), [])

    def test_invalid_results(self):
        plugin = self.make_plugin()
        filename = os.path.join(plugin._get_js_temp_directory(), "lib.js")
        batch = [(URL("http://www.w3af.com/lib.js"), 1, filename)]
        vulnerability = {"severity": "high", "identifiers": {"summary": "x"}}
        results = [
            {"component": "jquery", "vulnerabilities": [vulnerability]},
            {"version": "1.0", "vulnerabilities": [vulnerability]},
            {"component": "jquery", "version": "1.0", "vulnerabilities": []},
        ]

        plugin._json_to_kb(batch, {"data": [{"file": filename, "results": results}]})

        self.assertEqual(self.vulns(), [])


kb = DBKnowledgeBase()
