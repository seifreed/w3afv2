"""
test_spiderman.py

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
import socket
import time
import unittest
import urllib.error
import urllib.request
from multiprocessing.dummy import Process
from typing import ClassVar

from mitmproxy.test import tflow

from w3af.core.controllers.misc.get_unused_port import get_unused_port
from w3af.core.data.url.extended_urllib import ExtendedUrllib
from w3af.plugins.crawl.spider_man import (
    TERMINATE_FAVICON_URL,
    TERMINATE_URL,
    LoggingHandler,
    LoggingProxy,
    spider_man,
)
from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest

SITE_RE = r"http://(127\.0\.0\.1|localhost):\d+"


def _form_post(mock_response, request, uri, response_headers):
    response_headers["Content-Type"] = "text/html"
    text = request.parsed_body.get("text", [""])[0]
    return 200, response_headers, f"no such column: {text}"


class BrowserThread(Process):
    """
    Browse the site through the spider_man proxy, the same way a user would
    do with a web browser, and finish the session using the terminate URL.
    """

    def __init__(self, site_url, other_domain_url, proxy_port):
        super().__init__()
        self.responses = []
        self.site_url = site_url
        self.other_domain_url = other_domain_url
        self.proxy_port = proxy_port

    def run(self):
        self._wait_for_proxy()

        proxy = f"http://127.0.0.1:{self.proxy_port}/"
        proxy_support = urllib.request.ProxyHandler({"http": proxy})
        opener = urllib.request.build_opener(proxy_support)

        requests = (
            urllib.request.Request(self.site_url + "audit/"),
            urllib.request.Request(self.site_url + "audit/where_integer_qs.py?id=1"),
            urllib.request.Request(
                self.site_url + "audit/where_integer_form.py", data=b"text=abc"
            ),
            urllib.request.Request(self.other_domain_url + "audit/other_domain"),
            urllib.request.Request(TERMINATE_FAVICON_URL.url_string),
            urllib.request.Request(TERMINATE_URL.url_string),
        )

        for request in requests:
            self.responses.append(self._open(opener, request))

    def _wait_for_proxy(self):
        for _ in range(120):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    s.connect(("127.0.0.1", self.proxy_port))
                except OSError:
                    time.sleep(0.5)
                else:
                    return

    def _open(self, opener, request):
        try:
            response = opener.open(request)
        except urllib.error.HTTPError as http_error:
            return http_error.code, http_error.read()
        except OSError as error:
            return None, str(error).encode("utf-8")

        return response.status, response.read()


class TestSpiderman(PluginTest):

    target_url = "http://127.0.0.1/"

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(re.compile(SITE_RE + r"/$"), "index"),
        MockResponse(
            re.compile(SITE_RE + r"/audit/$"),
            "Trivial Blind SQL injection",
            headers={"Set-Cookie": "session=1234"},
        ),
        MockResponse(
            re.compile(SITE_RE + r"/audit/where_integer_qs\.py\?id=1$"),
            "reachable using a query string",
        ),
        MockResponse(
            re.compile(SITE_RE + r"/audit/where_integer_form\.py$"),
            _form_post,
            method="POST",
        ),
        MockResponse(re.compile(SITE_RE + r"/audit/other_domain$"), "other domain"),
    ]

    def test_spiderman_http(self):
        proxy_port = get_unused_port()
        site_url = f"http://127.0.0.1:{self.canned_server.port}/"
        other_domain_url = f"http://localhost:{self.canned_server.port}/"

        plugins = {
            "crawl": (
                PluginConfig(
                    "spider_man",
                    ("listen_port", proxy_port, PluginConfig.INT),
                ),
            )
        }

        browser = BrowserThread(site_url, other_domain_url, proxy_port)
        browser.start()

        self._scan(site_url, plugins)
        browser.join()

        statuses = [status for status, _ in browser.responses]
        bodies = [body.decode("utf-8", "replace") for _, body in browser.responses]

        self.assertEqual(statuses, [200, 200, 200, 200, 200, 200])

        expected_bodies = (
            "Trivial Blind SQL injection",
            "reachable using a query string",
            "no such column: abc",
            "other domain",
        )
        for expected, body in zip(expected_bodies, bodies, strict=False):
            self.assertIn(expected, body)

        self.assertIn("spider_man plugin finished its execution.", bodies[-1])

        kb_urls = {u.uri2url().url_string for u in self.kb.get_all_known_urls()}
        for path in ("audit/", "audit/where_integer_qs.py"):
            self.assertIn(site_url + path, kb_urls)

        post_requests = [
            fr
            for fr in self.kb.get_all_known_fuzzable_requests()
            if fr.get_method() == "POST"
        ]
        self.assertEqual(len(post_requests), 1, post_requests)
        self.assertEqual(post_requests[0].get_raw_data()["text"], ["abc"])


class TestSpidermanOptions(unittest.TestCase):

    def test_set_options(self):
        plugin = spider_man()

        options = plugin.get_options()
        options["listen_address"].set_value("127.0.0.2")
        options["listen_port"].set_value("8081")
        plugin.set_options(options)

        options = plugin.get_options()
        self.assertEqual(options["listen_address"].get_value(), "127.0.0.2")
        self.assertEqual(options["listen_port"].get_value(), 8081)

    def test_long_desc(self):
        self.assertIn("listen_port", spider_man().get_long_desc())


class TestLoggingHandlerUnreachableSite(unittest.TestCase):

    def test_unreachable_site_returns_error_page(self):
        uri_opener = ExtendedUrllib()
        self.addCleanup(uri_opener.end)

        plugin = spider_man()
        proxy = LoggingProxy(
            "127.0.0.1", 0, uri_opener, plugin=plugin, target_domain="127.0.0.1"
        )
        handler = LoggingHandler(None, uri_opener, proxy)

        flow = tflow.tflow()
        flow.request.host = "127.0.0.1"
        flow.request.port = get_unused_port()
        flow.request.path = "/unreachable"

        handler.handle_request_in_thread(flow)

        self.assertEqual(flow.response.status_code, 500)
        self.assertIn(b"/unreachable", flow.response.content)
        self.assertEqual(plugin.output_queue.qsize(), 1)
