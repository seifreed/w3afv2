"""
test_plugin_bases.py

Copyright 2026 w3af contributors

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

import w3af.core.controllers.output_manager as om
from w3af.core.controllers.core_helpers.fingerprint_404 import (
    fingerprint_404_singleton,
)
from w3af.core.controllers.plugins.crawl_plugin import CrawlPlugin
from w3af.core.controllers.plugins.evasion_plugin import EvasionPlugin
from w3af.core.controllers.plugins.grep_plugin import GrepPlugin
from w3af.core.controllers.plugins.infrastructure_plugin import InfrastructurePlugin
from w3af.core.controllers.plugins.mangle_plugin import ManglePlugin
from w3af.core.controllers.plugins.output_plugin import OutputPlugin
from w3af.core.controllers.tests.local_http_server import LocalHTTPServer, Reply
from w3af.core.controllers.tests.recording_output import start_recording_output
from w3af.core.data.dc.headers import Headers
from w3af.core.data.kb.config import Config
from w3af.core.data.options.opt_factory import opt_factory
from w3af.core.data.options.option_list import OptionList
from w3af.core.data.options.option_types import BOOL
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.request.fuzzable_request import FuzzableRequest
from w3af.core.data.url.extended_urllib import ExtendedUrllib
from w3af.core.data.url.http_response import HTTPResponse
from w3af.core.exceptions import (
    BaseFrameworkException,
    FourOhFourDetectionException,
)
from w3af.core.filesystem import create_temp_dir

FREQ = FuzzableRequest(URL("http://127.0.0.1/"))


EXISTING_PAGES = ("/exists/page", "/exists/other")


def site_with_pages(method, path):
    if path in EXISTING_PAGES:
        return Reply(body="<html><body>An existing page with content</body></html>")
    return Reply(status=404, body="<html><body>Page not found</body></html>")


class finds_nothing(InfrastructurePlugin):
    """
    Returns the URL it was asked to discover.
    """

    def discover(self, fuzzable_request, debugging_id):
        return fuzzable_request.get_url()


class spider(CrawlPlugin):
    """
    Returns the URL it was asked to crawl.
    """

    def crawl(self, fuzzable_request, debugging_id):
        return fuzzable_request.get_url()


class failing_404_detection(GrepPlugin, CrawlPlugin, InfrastructurePlugin):
    """
    Fails while detecting 404 pages in every phase.
    """

    def fail(self, *args):
        raise FourOhFourDetectionException("404 detection failed")

    grep = crawl = discover = fail


class priority_mangle(ManglePlugin):
    """
    Mangle plugin with a custom priority.
    """

    def __init__(self, priority):
        ManglePlugin.__init__(self)
        self._priority = priority


class TestNotImplementedMethods(unittest.TestCase):
    def test_grep(self):
        self.assertRaisesRegex(
            NotImplementedError, "must implement", GrepPlugin().grep, FREQ, None
        )

    def test_evasion(self):
        plugin = EvasionPlugin()

        self.assertRaises(NotImplementedError, plugin.modify_request, None)
        self.assertRaises(NotImplementedError, plugin.get_priority)

    def test_mangle(self):
        plugin = ManglePlugin()

        self.assertRaises(NotImplementedError, plugin.mangle_request, None)
        self.assertRaises(NotImplementedError, plugin.mangle_response, None)

    def test_infrastructure(self):
        self.assertRaises(
            BaseFrameworkException, InfrastructurePlugin().discover, FREQ, "did"
        )

    def test_crawl(self):
        self.assertRaises(BaseFrameworkException, CrawlPlugin().crawl, FREQ, "did")

    def test_output(self):
        plugin = OutputPlugin()

        for method in (
            plugin.debug,
            plugin.information,
            plugin.error,
            plugin.vulnerability,
            plugin.console,
        ):
            self.assertRaises(NotImplementedError, method, "message")


class TestPluginTypes(unittest.TestCase):
    def test_types(self):
        types = [
            plugin().get_type()
            for plugin in (
                GrepPlugin,
                EvasionPlugin,
                ManglePlugin,
                InfrastructurePlugin,
                CrawlPlugin,
                OutputPlugin,
            )
        ]

        self.assertEqual(
            types, ["grep", "evasion", "mangle", "infrastructure", "crawl", "output"]
        )


class TestWrappers(unittest.TestCase):
    def test_discover_wrapper_uses_a_copy(self):
        plugin = finds_nothing()
        plugin.set_output(om.out)
        self.assertEqual(plugin.discover_wrapper(FREQ, "did"), FREQ.get_url())

    def test_crawl_discover_wrapper(self):
        start_recording_output()
        plugin = spider()
        plugin.set_output(om.out)

        self.assertEqual(plugin.discover_wrapper(FREQ, "did"), FREQ.get_url())

    def test_404_detection_errors_are_logged(self):
        recorder = start_recording_output()
        plugin = failing_404_detection()
        plugin.set_output(om.out)

        self.assertIsNone(plugin.grep_wrapper(FREQ, None))
        self.assertIsNone(CrawlPlugin.discover_wrapper(plugin, FREQ, "did"))
        self.assertIsNone(InfrastructurePlugin.discover_wrapper(plugin, FREQ, "did"))

        self.assertEqual(
            [m for m in recorder.messages_of("debug") if m == "404 detection failed"],
            ["404 detection failed"] * 3,
        )


class TestCrawlHTTPGetAndParse(unittest.TestCase):
    def setUp(self):
        create_temp_dir()
        self.uri_opener = ExtendedUrllib()
        self.addCleanup(self.uri_opener.end)
        fingerprint_404_singleton(om.out, cf, cleanup=True).set_url_opener(
            self.uri_opener
        )
        self.addCleanup(fingerprint_404_singleton, cleanup=True)

        self.site = LocalHTTPServer(site_with_pages).start()
        self.addCleanup(self.site.close)

        self.plugin = spider()
        self.plugin.set_output(om.out)
        self.plugin.set_configuration(cf)
        self.plugin.set_url_opener(self.uri_opener)
        self.successes = []

    def on_success(self, response, url):
        self.successes.append(url)

    def test_existing_page_is_queued(self):
        url = URL(self.site.url("/exists/page"))

        response = self.plugin.http_get_and_parse(url, on_success=self.on_success)

        self.assertEqual(response.get_code(), 200)
        self.assertEqual(self.plugin.output_queue.get_nowait().get_url(), url)
        self.assertEqual(self.successes, [url])

    def test_existing_page_without_callback(self):
        url = URL(self.site.url("/exists/other"))

        self.plugin.http_get_and_parse(url)

        self.assertEqual(self.plugin.output_queue.get_nowait().get_url(), url)

    def test_missing_page_is_ignored(self):
        response = self.plugin.http_get_and_parse(
            URL(self.site.url("/missing")), on_success=self.on_success
        )

        self.assertEqual(response.get_code(), 404)
        self.assertTrue(self.plugin.output_queue.empty())
        self.assertEqual(self.successes, [])

    def test_http_get_does_not_queue(self):
        url = URL(self.site.url("/missing"))

        response = self.plugin.http_get(url, on_success=self.on_success)

        self.assertEqual(response.get_code(), 404)
        self.assertTrue(self.plugin.output_queue.empty())
        self.assertEqual(self.successes, [url])

    def test_http_get_without_callback(self):
        response = self.plugin.http_get(URL(self.site.url("/exists/page")))

        self.assertEqual(response.get_code(), 200)


class TestManglePlugin(unittest.TestCase):
    def test_priority_ordering(self):
        low, high = priority_mangle(10), priority_mangle(90)

        self.assertEqual(ManglePlugin().get_priority(), 20)
        self.assertTrue(high > low)
        self.assertTrue(low < high)
        self.assertEqual(sorted([high, low]), [low, high])
        self.assertTrue(priority_mangle(10) == low)

    def test_url_opener_is_ignored(self):
        plugin = ManglePlugin()
        plugin.set_url_opener(ExtendedUrllib())

        self.assertIsNone(plugin._uri_opener)

    def test_fix_existing_content_length(self):
        url = URL("http://127.0.0.1/")
        headers = Headers([("content-length", "1")])
        response = HTTPResponse(200, "mangled body", headers, url, url)

        fixed = ManglePlugin()._fix_content_len(response)

        self.assertEqual(fixed.get_headers()["content-length"], "12")

    def test_add_missing_content_length(self):
        url = URL("http://127.0.0.1/")
        response = HTTPResponse(200, "body", Headers(), url, url)

        fixed = ManglePlugin()._fix_content_len(response)

        self.assertEqual(fixed.get_headers()["Content-Length"], "4")


class TestEvasionPlugin(unittest.TestCase):
    def test_url_opener_is_ignored(self):
        plugin = EvasionPlugin()
        plugin.set_url_opener(ExtendedUrllib())

        self.assertIsNone(plugin._uri_opener)


class TestOutputPlugin(unittest.TestCase):
    def test_optional_hooks_do_nothing(self):
        plugin = OutputPlugin()

        self.assertIsNone(plugin.log_http(None, None))
        self.assertIsNone(plugin.log_crash("crash"))
        self.assertIsNone(plugin.log_enabled_plugins({}, {}))
        self.assertIsNone(plugin.flush())
        self.assertEqual(plugin.get_plugin_deps(), [])

    def test_clean_string(self):
        plugin = OutputPlugin()

        self.assertEqual(plugin._clean_string(None), "")
        self.assertEqual(plugin._clean_string("a\0b\tc\nd\re"), "a\\0b\\tc\\nd\\re")

    def test_get_caller(self):
        self.assertEqual(
            OutputPlugin().get_caller(which_stack_item=1), "test_plugin_bases"
        )

    def test_get_caller_outside_the_stack(self):
        self.assertEqual(
            OutputPlugin().get_caller(which_stack_item=10000), "unknown-caller"
        )

    def test_create_plugin_info(self):
        options = OptionList()
        options.add(opt_factory("only_forward", True, "Only forward", BOOL))

        info = OutputPlugin()._create_plugin_info(
            "crawl", ["web_spider", "robots_txt"], {"web_spider": options}
        )

        self.assertEqual(
            info,
            "plugins\n"
            "    crawl web_spider, robots_txt\n"
            "    crawl config web_spider\n"
            "        set only_forward True\n"
            "        back\n"
            "    back\n",
        )

    def test_create_plugin_info_without_plugins(self):
        self.assertEqual(OutputPlugin()._create_plugin_info("audit", [], {}), "")


cf = Config()
