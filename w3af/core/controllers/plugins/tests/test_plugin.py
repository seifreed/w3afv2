"""
test_plugin.py

Copyright 2006 Andres Riancho

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

import w3af.core.data.kb.knowledge_base as kb
from w3af.core.controllers.plugins.plugin import Plugin
from w3af.core.controllers.tests.local_http_server import (
    LocalHTTPServer,
    Reply,
    closed_local_port,
)
from w3af.core.controllers.tests.recording_output import start_recording_output
from w3af.core.controllers.threads.threadpool import Pool
from w3af.core.data.kb.info import Info
from w3af.core.data.kb.info_set import InfoSet
from w3af.core.data.options.option_list import OptionList
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.request.fuzzable_request import FuzzableRequest
from w3af.core.data.url.exceptions import HTTPRequestException
from w3af.core.data.url.extended_urllib import ExtendedUrllib
from w3af.plugins.crawl.find_dvcs import find_dvcs
from w3af.plugins.crawl.web_spider import web_spider


def hello_site(method, path):
    return Reply(body=f"hello {path}")


class undocumented(Plugin):
    pass


undocumented.__doc__ = None


class strict_errors(Plugin):
    """
    Re-raises every HTTP request error.
    """

    def handle_url_error(self, uri, http_exception):
        return True, None


class FindingSet(InfoSet):
    ITAG = "finding"
    TEMPLATE = "{{ uris|length }} URLs have the same finding"


def new_info(url):
    info = Info("Interesting finding", "A finding in a test", [1], "plugin")
    info.set_url(URL(url))
    info[FindingSet.ITAG] = "same"
    return info


class TestPlugin(unittest.TestCase):
    def setUp(self):
        kb.kb.cleanup()
        self.addCleanup(kb.kb.cleanup)

    def test_get_desc_trivial(self):
        p = Plugin()
        p.__doc__ = "abc"

        self.assertEqual(p.get_desc(), "abc")

    def test_get_desc_complex(self):
        p = find_dvcs()
        desc = p.get_desc()

        self.assertNotIn("author", desc)

    def test_get_desc_without_docstring(self):
        self.assertEqual(
            undocumented().get_desc(), "No description available for this plugin."
        )

    def test_get_long_desc_must_be_implemented(self):
        self.assertRaises(NotImplementedError, Plugin().get_long_desc)

    def test_equal_plugins_share_set_membership(self):
        disabled = {web_spider()}

        self.assertIn(web_spider(), disabled)
        self.assertNotIn(find_dvcs(), disabled)

    def test_defaults(self):
        plugin = Plugin()

        self.assertIsInstance(plugin.get_options(), OptionList)
        self.assertEqual(len(plugin.get_options()), 0)
        self.assertIsNone(plugin.set_options(OptionList()))
        self.assertEqual(plugin.get_plugin_deps(), [])
        self.assertEqual(plugin.get_type(), "plugin")
        self.assertEqual(plugin.get_name(), "Plugin")
        self.assertEqual(repr(plugin), "<plugin.Plugin>")
        self.assertIsNone(plugin.end())

    def test_core_and_worker_pool(self):
        plugin = Plugin()
        pool = Pool(1, worker_names="PluginTestWorker")
        self.addCleanup(pool.terminate_join)

        plugin.set_w3af_core("core")
        plugin.set_worker_pool(pool)

        self.assertEqual(plugin.get_w3af_core(), "core")
        self.assertIs(plugin.worker_pool, pool)

    def test_kb_append_uniq(self):
        plugin = Plugin()
        recorder = start_recording_output()

        self.assertTrue(
            plugin.kb_append_uniq("a", "b", new_info("http://w3af.org/"), "URL")
        )
        self.assertFalse(
            plugin.kb_append_uniq("a", "b", new_info("http://w3af.org/"), "URL")
        )

        self.assertEqual(len(kb.kb.get("a", "b")), 1)
        self.assertEqual(len(recorder.messages_of("vulnerability")), 1)

    def test_kb_append_uniq_group(self):
        plugin = Plugin()
        recorder = start_recording_output()

        for url in ("http://w3af.org/1", "http://w3af.org/2"):
            plugin.kb_append_uniq_group("a", "b", new_info(url), FindingSet)

        info_sets = kb.kb.get("a", "b")
        self.assertEqual(len(info_sets), 1)
        self.assertIsInstance(info_sets[0], FindingSet)
        self.assertEqual(len(info_sets[0].infos), 2)
        self.assertEqual(len(recorder.messages_of("vulnerability")), 1)

    def test_kb_append(self):
        plugin = Plugin()
        recorder = start_recording_output()

        plugin.kb_append("a", "b", new_info("http://w3af.org/"))
        plugin.kb_append("a", "b", new_info("http://w3af.org/"))

        self.assertEqual(len(kb.kb.get("a", "b")), 2)
        self.assertEqual(len(recorder.messages_of("vulnerability")), 2)

    def test_handle_url_error_returns_no_content(self):
        plugin = Plugin()
        recorder = start_recording_output()
        url = URL("http://w3af.org/")

        re_raise, response = plugin.handle_url_error(url, Exception("boom"))

        self.assertFalse(re_raise)
        self.assertEqual(response.get_code(), 204)
        self.assertIn('Exception: "boom"', recorder.messages_of("error")[0])


class TestSendMutantsInThreads(unittest.TestCase):
    def setUp(self):
        self.plugin = Plugin()
        pool = Pool(2, worker_names="PluginTestWorker")
        self.addCleanup(pool.terminate_join)
        self.plugin.set_worker_pool(pool)
        self.results = []

    def collect(self, mutant, response):
        self.results.append((mutant, response))

    def test_list_of_mutants(self):
        self.plugin._send_mutants_in_threads(
            lambda x, debugging_id: x * 2, [1, 2, 3], self.collect, debugging_id="d"
        )

        self.assertEqual(sorted(self.results), [(1, 2), (2, 4), (3, 6)])

    def test_iterator_of_mutants(self):
        self.plugin._send_mutants_in_threads(lambda x: -x, iter([1, 2]), self.collect)

        self.assertEqual(sorted(self.results), [(1, -1), (2, -2)])

    def test_thread_exceptions_are_raised(self):
        def fail(mutant):
            raise ValueError(f"failed {mutant}")

        with self.assertRaisesRegex(ValueError, "failed 1"):
            self.plugin._send_mutants_in_threads(fail, [1], self.collect)


class TestUrlOpenerProxy(unittest.TestCase):
    def setUp(self):
        self.uri_opener = ExtendedUrllib()
        self.addCleanup(self.uri_opener.end)

    def closed_url(self):
        return URL(f"http://127.0.0.1:{closed_local_port()}/")

    def test_successful_request(self):
        plugin = Plugin()
        plugin.set_url_opener(self.uri_opener)

        with LocalHTTPServer(hello_site) as site:
            response = plugin._uri_opener.GET(URL(site.url("/x")))

        self.assertEqual(response.get_body(), "hello /x")

    def test_failed_url_request_returns_no_content(self):
        plugin = Plugin()
        plugin.set_url_opener(self.uri_opener)
        start_recording_output()

        response = plugin._uri_opener.GET(self.closed_url())

        self.assertEqual(response.get_code(), 204)

    def test_failed_fuzzable_request_returns_no_content(self):
        plugin = Plugin()
        plugin.set_url_opener(self.uri_opener)
        recorder = start_recording_output()
        url = self.closed_url()

        response = plugin._uri_opener.send_mutant(FuzzableRequest(url))

        self.assertEqual(response.get_code(), 204)
        self.assertIn(str(url), recorder.messages_of("error")[0])

    def test_plugin_can_ask_to_reraise(self):
        plugin = strict_errors()
        plugin.set_url_opener(self.uri_opener)

        self.assertRaises(
            HTTPRequestException, plugin._uri_opener.GET, self.closed_url()
        )

    def test_methods_which_are_not_wrapped(self):
        plugin = Plugin()
        plugin.set_url_opener(self.uri_opener)

        self.assertEqual(plugin._uri_opener.get_cookies, self.uri_opener.get_cookies)

    def test_attributes_are_returned_as_is(self):
        plugin = Plugin()
        plugin.set_url_opener(self.uri_opener)

        self.assertIs(plugin._uri_opener.settings, self.uri_opener.settings)
