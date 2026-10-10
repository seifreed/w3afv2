"""
test_crawl_infrastructure.py

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

import re
import unittest

import w3af.core.data.kb.config as cf
import w3af.core.data.kb.knowledge_base as kb
from w3af.core.constants import POISON_PILL
from w3af.core.controllers.core_helpers.consumers.crawl_infrastructure import (
    CrawlInfrastructure,
)
from w3af.core.controllers.core_helpers.consumers.tests.consumer_plugins import (
    CrashingObserver,
    crashing_crawl,
    drain_results,
    framework_error_crawl,
    list_returning_crawl,
    queueing_crawl,
    reported_errors,
    run_once_crawl,
    stopping_crawl,
    wait_until,
)
from w3af.core.controllers.tests.local_http_server import LocalHTTPServer, Reply
from w3af.core.controllers.tests.recording_output import start_recording_output
from w3af.core.controllers.w3af_core import w3afCore
from w3af.core.data.dc.headers import Headers
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.request.fuzzable_request import FuzzableRequest
from w3af.plugins.tests.helper import PluginConfig, PluginTest

BASE = "http://127.0.0.1:8000/"
NEVER = 60
FORM_HEADERS = Headers([("content-type", "application/x-www-form-urlencoded")])


def request(path):
    return FuzzableRequest(URL(BASE + path))


def form(path):
    return FuzzableRequest.from_parts(
        URL(BASE + path), "POST", "user=a&pass=b", FORM_HEADERS
    )


TREE_SIZE = 31


def binary_tree_site(method, path):
    """
    Page N links to pages 2N+1 and 2N+2, the site has TREE_SIZE pages
    """
    name = path.strip("/") or "0"
    if not name.isdigit():
        return Reply(status=404, body="Not found")

    page = int(name)
    children = [child for child in (page * 2 + 1, page * 2 + 2) if child < TREE_SIZE]
    links = "".join(f'<a href="/{child}">{child}</a>' for child in children)
    return Reply(body=f"<html><body>{links}</body></html>")


class TestTimeLimit(PluginTest):
    def setUp(self):
        super().setUp()
        self.site = LocalHTTPServer(binary_tree_site).start()
        self.addCleanup(self.site.close)

    def crawl(self, max_discovery_time):
        self._scan(
            self.site.url("/"),
            {"crawl": (PluginConfig("web_spider"),)},
            misc_settings={"max_discovery_time": max_discovery_time},
        )
        return {url.url_string for url in self.kb.get_all_known_urls()}

    def test_spider_crawls_the_whole_site_within_time_limit(self):
        expected = {self.site.url("/")}
        expected.update(self.site.url(f"/{page}") for page in range(1, TREE_SIZE))

        self.assertEqual(self.crawl(max_discovery_time=10), expected)

    def test_spider_stops_at_time_limit(self):
        self.assertEqual(self.crawl(max_discovery_time=0), {self.site.url("/")})


class CrawlConsumerTest(unittest.TestCase):
    def setUp(self):
        self.core = w3afCore()
        self.addCleanup(self.core.worker_pool.terminate_join)
        self.core.status.start()
        cf.cf.save("baseURLs", [URL(BASE)])
        self.addCleanup(cf.cf.save, "baseURLs", [])
        self.addCleanup(kb.kb.cleanup)
        self.recorder = start_recording_output()

    def start_consumer(self, plugins, max_discovery_time=NEVER, observer=None):
        for plugin in plugins:
            self.core.plugins.plugins[plugin.get_type()].append(plugin)

        consumer = CrawlInfrastructure(
            plugins, self.core, max_discovery_time, knowledge_base=kb.kb
        )
        if observer is not None:
            consumer.add_observer(observer)
        consumer.start()
        return consumer

    def messages(self, kind):
        return self.recorder.messages_of(kind)

    def assert_end_logged(self, plugin_name, suffix):
        expected = re.compile(
            rf"Spent \d+\.\d\d seconds running {plugin_name}\.end\(\)"
            + re.escape(suffix)
            + "$"
        )
        self.assertTrue(any(expected.match(m) for m in self.messages("debug")))


class TestRouting(CrawlConsumerTest):
    def test_new_fuzzable_requests_are_routed(self):
        new_page = request("new")
        new_form = form("login")
        plugin = queueing_crawl(
            items=[
                new_page,
                "not a fuzzable request",
                FuzzableRequest(URL("http://127.0.0.2/out-of-scope")),
                request("new"),
                new_form,
                form("login"),
            ]
        )
        consumer = self.start_consumer([plugin], observer=CrashingObserver())

        consumer.in_queue_put(request(""))
        consumer.join()

        results = drain_results(consumer)
        routed = [r for r in results if isinstance(r, tuple)]
        self.assertEqual(
            routed,
            [("queueing_crawl", None, new_page), ("queueing_crawl", None, new_form)],
        )
        self.assertEqual(results[-1], POISON_PILL)
        self.assertEqual(plugin.crawled, [BASE])
        self.assertEqual(plugin.end_calls, 1)
        self.assertEqual(self.core.plugins.plugins["crawl"], [])

        errors = [
            (result.plugin, str(result.exception))
            for result in results
            if not isinstance(result, (tuple, int))
        ]
        self.assertEqual(
            errors,
            [
                (
                    "CrawlInfrastructure._run_observers()",
                    "crawl observer failed",
                ),
                (
                    "queueing_crawl",
                    "The queueing_crawl plugin did NOT return a FuzzableRequest.",
                ),
            ],
        )

        debug_messages = self.messages("debug")
        self.assertIn(
            f'Ignoring reference "{BASE}new" since it is simply a variant of'
            " another URL seen before.",
            debug_messages,
        )
        self.assertIn(
            f'Ignoring form "{BASE}login" with parameters [user, pass] since it'
            " is simply a variant of another form seen before.",
            debug_messages,
        )
        self.assert_end_logged("queueing_crawl", "")

        information = self.messages("information")
        self.assertIn(
            f'New URL found by queueing_crawl plugin: "{BASE}new"', information
        )
        self.assertIn("Found 2 URLs and 2 different injections points.", information)
        self.assertIn(f"- {BASE}login", information)

    def test_time_limit_finishes_the_consumer(self):
        first = request("first")
        plugin = queueing_crawl()
        plugin.output_queue.put(first)
        consumer = CrawlInfrastructure(
            [plugin], self.core, max_discovery_time=0, knowledge_base=kb.kb
        )
        consumer.in_queue_put(request("a"))
        consumer.in_queue_put(request("b"))

        consumer.start()
        wait_until(lambda: not consumer.is_alive())

        # The routing threads race, the time limit can be detected by one of
        # them before the other one finishes routing the plugin result. The
        # time limit and the consumer teardown send one POISON_PILL each.
        results = drain_results(consumer)
        expected = [("queueing_crawl", None, first), POISON_PILL, POISON_PILL]
        self.assertEqual(sorted(results, key=str), sorted(expected, key=str))
        self.assertEqual(plugin.output_queue.qsize(), 0)
        self.assertTrue(consumer.has_finished())
        self.assertIn(
            "Maximum crawl time limit hit, no new URLs will be added to the queue.",
            self.messages("information"),
        )

        # Only one of the two queued requests was crawled, the other one was
        # removed from the input queue when the time limit was hit
        (crawled,) = plugin.crawled
        self.assertIn(crawled, (BASE + "a", BASE + "b"))

        # Nothing else is crawled or routed once the consumer stopped
        plugin.output_queue.put(request("late"))
        self.assertTrue(consumer._should_stop_discovery())
        consumer._consume(request("ignored"))
        consumer._route_all_plugin_results()
        consumer._plugin_finished_cb(((plugin, first), None))
        self.assertEqual(plugin.crawled, [crawled])
        self.assertEqual(plugin.output_queue.qsize(), 1)
        self.assertEqual(drain_results(consumer), [])

        consumer.join()
        self.assertEqual(self.core.plugins.plugins["crawl"], [])


class TestPluginErrors(CrawlConsumerTest):
    def test_plugin_errors_are_reported(self):
        plugins = [
            framework_error_crawl(),
            crashing_crawl(),
            list_returning_crawl(),
            stopping_crawl(),
        ]
        consumer = self.start_consumer(plugins)

        consumer.in_queue_put(request(""))
        consumer.join()

        errors = sorted(reported_errors(consumer))
        self.assertEqual(errors[:2], sorted(errors[:2]))
        self.assertEqual(
            [plugin for plugin, _ in errors],
            ["crashing_crawl", "crashing_crawl", "list_returning_crawl"],
        )
        self.assertIn(("crashing_crawl", "crawl failed"), errors)
        self.assertIn(("crashing_crawl", "crawl end failed"), errors)
        self.assertRegex(
            errors[2][1], r"The list_returning_crawl plugin did NOT return None"
        )

        (error,) = self.messages("error")
        self.assertRegex(
            error,
            r'An exception was found while running "framework_error_crawl" with'
            r' ".*": "crawl framework error" \(did: \w+\)',
        )
        self.assert_end_logged(
            "stopping_crawl", " until a scan must stop exception was raised"
        )
        self.assert_end_logged(
            "crashing_crawl", " until an unhandled exception was found"
        )
        self.assertIn("No URLs found during crawl phase.", self.messages("information"))

    def test_run_once_plugins_are_disabled(self):
        plugin = run_once_crawl()
        other = queueing_crawl()
        consumer = self.start_consumer([plugin, other])

        consumer.in_queue_put(request(""))
        wait_until(lambda: plugin in consumer._disabled_plugins)
        consumer._route_all_plugin_results()
        consumer.in_queue_put(request("again"))
        consumer.join()

        self.assertEqual(plugin.end_calls, 1)
        self.assertEqual(other.crawled, [BASE, BASE + "again"])
        self.assertIn(
            'The infrastructure plugin: "run_once_crawl" wont be run anymore.',
            self.messages("debug"),
        )

    def test_remove_unknown_plugin(self):
        plugin = run_once_crawl()
        consumer = CrawlInfrastructure([plugin], self.core, NEVER, knowledge_base=kb.kb)
        self.addCleanup(consumer._shutdown_threadpool)

        consumer._remove_discovery_plugin(plugin)

        self.assertEqual(consumer._disabled_plugins, set())
        self.assertFalse(hasattr(plugin, "end_calls"))
