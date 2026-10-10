"""
test_xurllib.py

Copyright 2011 Andres Riancho

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
import queue
import time
import unittest
from multiprocessing.dummy import Process

import pytest

from w3af import ROOT_PATH
from w3af.core.controllers.misc.get_unused_port import get_unused_port
from w3af.core.data.dc.headers import Headers
from w3af.core.data.dc.urlencoded_form import URLEncodedForm
from w3af.core.data.kb.config import Config
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.url.constants import MAX_ERROR_COUNT
from w3af.core.data.url.exceptions import HTTPRequestException
from w3af.core.data.url.extended_urllib import ExtendedUrllib
from w3af.core.data.url.http_response import DEFAULT_WAIT_TIME
from w3af.core.data.url.tests.helpers.raw_handlers import (
    EmptyTCPHandler,
    Ok200Handler,
    closed_port,
)
from w3af.core.data.url.tests.helpers.route_server import Response, RouteServer, echo
from w3af.core.data.url.tests.helpers.ssl_daemon import RawSSLDaemon, SSLServer
from w3af.core.data.url.tests.helpers.upper_daemon import UpperDaemon
from w3af.core.exceptions import (
    BaseFrameworkException,
    ScanMustStopByUserRequest,
    ScanMustStopException,
)
from w3af.core.filesystem import get_temp_dir
from w3af.plugins.evasion.rnd_case import rnd_case
from w3af.plugins.evasion.rnd_path import rnd_path

INDEX = "<title>local test application</title>"
BIG_BODY = b'{"jquery": "' + b"x" * 500000 + b'"}'


@pytest.mark.smoke
class TestXUrllib(unittest.TestCase):

    def setUp(self):
        self.uri_opener = ExtendedUrllib(configuration=cf)
        self.addCleanup(self.uri_opener.end)
        self.addCleanup(self.uri_opener.settings.set_default_values)

        routes = {
            "/": Response(200, INDEX),
            "/echo": echo,
            "/big.json": Response(200, BIG_BODY, content_type="application/json"),
        }
        self.server = RouteServer.serve_for(self, routes)
        self.ssl_server = RouteServer.serve_for(self, routes, use_tls=True)

    def test_evasion_plugins_are_sorted_by_priority(self):
        evasion_plugins = [rnd_case(), rnd_path()]

        self.uri_opener.set_evasion_plugins(evasion_plugins)

        priorities = [
            plugin.get_priority() for plugin in self.uri_opener._evasion_plugins
        ]
        self.assertEqual(priorities, [0, 25])

    def test_basic(self):
        http_response = self.uri_opener.GET(URL(self.server.url()), cache=False)

        self.assertIn(INDEX, http_response.body)
        self.assertGreaterEqual(http_response.id, 1)

    def test_basic_ssl(self):
        http_response = self.uri_opener.GET(URL(self.ssl_server.url()), cache=False)

        self.assertIn(INDEX, http_response.body)
        self.assertGreaterEqual(http_response.id, 1)

    def test_download_over_size_limit(self):
        url = URL(self.ssl_server.url("/big.json"))

        http_response = self.uri_opener.GET(
            url, cache=False, binary_response=True, respect_size_limit=False
        )

        self.assertEqual(http_response.get_raw_body(), BIG_BODY)
        self.assertEqual(cf.get("max_file_size"), 400000)

    def test_size_limit_is_restored_when_request_fails(self):
        url = URL(f"http://127.0.0.1:{closed_port()}/")

        self.assertRaises(
            HTTPRequestException, self.uri_opener.GET, url, respect_size_limit=False
        )
        self.assertEqual(cf.get("max_file_size"), 400000)

    def test_cache(self):
        url = URL(self.server.url())

        first = self.uri_opener.GET(url, cache=True)
        second = self.uri_opener.GET(url, cache=True)

        self.assertIn(INDEX, first.body)
        self.assertIn(INDEX, second.body)
        self.assertFalse(first.get_from_cache())
        self.assertTrue(second.get_from_cache())
        self.assertEqual(len(self.server.requests), 1)

    def test_qs_params(self):
        url = URL(self.server.url("/echo?text=123456abc"))
        http_response = self.uri_opener.GET(url, cache=False)
        self.assertIn("text=123456abc", http_response.body)

        url = URL(self.server.url("/echo?text=root:x:0"))
        http_response = self.uri_opener.GET(url, cache=False)
        self.assertIn("text=root:x:0", http_response.body)

    def test_GET_with_post_data(self):
        data = "abc=123&def=456"
        response = self.uri_opener.GET(URL(self.server.url("/")), data=data)

        self.assertEqual(response.get_code(), 200)
        self.assertEqual(response.get_body(), INDEX)

        request = self.server.requests[-1]
        self.assertEqual(request.method, "GET")
        self.assertEqual(request.headers["Content-Length"], str(len(data)))
        self.assertEqual(request.body, data.encode())
        self.assertEqual(request.path, "/")

    def test_GET_with_post_data_and_qs(self):
        data = "abc=123&def=456"
        response = self.uri_opener.GET(URL(self.server.url("/?qs=1")), data=data)

        self.assertEqual(response.get_code(), 200)

        request = self.server.requests[-1]
        self.assertEqual(request.method, "GET")
        self.assertEqual(request.headers["Content-Length"], str(len(data)))
        self.assertEqual(request.body, data.encode())
        self.assertEqual(request.path, "/?qs=1")

    def test_post(self):
        data = URLEncodedForm()
        data["text"] = ["123456abc"]

        url = URL(self.server.url("/echo"))
        http_response = self.uri_opener.POST(url, data, cache=False)

        self.assertIn("text=123456abc", http_response.body)
        self.assertEqual(self.server.requests[-1].method, "POST")

    def test_post_special_chars(self):
        test_data = 'abc<def>"-á-'

        data = URLEncodedForm()
        data["text"] = [test_data]

        url = URL(self.server.url("/echo"))
        http_response = self.uri_opener.POST(url, data, cache=False)
        self.assertIn(f"text={test_data}", http_response.body)

    def test_file_proto(self):
        url = URL("file://foo/bar.txt")
        self.assertRaises(HTTPRequestException, self.uri_opener.GET, url)

    def test_url_port_closed(self):
        url = URL(f"http://127.0.0.1:{closed_port()}/")
        self.assertRaises(HTTPRequestException, self.uri_opener.GET, url)

    def test_url_port_not_http(self):
        upper_daemon = UpperDaemon(EmptyTCPHandler)
        upper_daemon.start()
        upper_daemon.wait_for_start()

        url = URL(f"http://127.0.0.1:{upper_daemon.get_port()}/")

        with self.assertRaises(HTTPRequestException) as raised:
            self.uri_opener.GET(url)

        self.assertEqual(raised.exception.value, "Bad HTTP response status line: ''")

    def test_url_port_not_http_many(self):
        upper_daemon = UpperDaemon(EmptyTCPHandler)
        upper_daemon.start()
        upper_daemon.wait_for_start()

        self.uri_opener.settings.set_max_http_retries(0)

        url = URL(f"http://127.0.0.1:{upper_daemon.get_port()}/")
        http_request_e = 0
        scan_must_stop_e = 0

        for _ in range(MAX_ERROR_COUNT):
            try:
                self.uri_opener.GET(url)
            except HTTPRequestException:
                http_request_e += 1
            except ScanMustStopException:
                scan_must_stop_e += 1
                break

        self.assertEqual(scan_must_stop_e, 1)
        self.assertEqual(http_request_e, 9)

    def test_get_wait_time(self):
        """
        Asserts that all the responses coming out of the extended urllib have a
        get_wait_time different from the default.
        """
        http_response = self.uri_opener.GET(URL(self.server.url()), cache=False)
        self.assertNotEqual(http_response.get_wait_time(), DEFAULT_WAIT_TIME)

    def test_ssl_tls(self):
        ssl_daemon = RawSSLDaemon(Ok200Handler)
        ssl_daemon.start()
        ssl_daemon.wait_for_start()

        url = URL(f"https://127.0.0.1:{ssl_daemon.get_port()}/")

        resp = self.uri_opener.GET(url)
        self.assertEqual(resp.get_body(), Ok200Handler.body.encode())

    def test_ssl_sni(self):
        """
        Test if our HTTP client supports SSL SNI
        """
        url = URL(self.ssl_server.url(host="localhost"))

        resp = self.uri_opener.GET(url)

        self.assertIn(INDEX, resp.get_body())
        self.assertIn("localhost", self.ssl_server.server_names)

    def test_ssl_fail_when_requesting_http(self):
        http_daemon = UpperDaemon(Ok200Handler)
        http_daemon.start()
        http_daemon.wait_for_start()

        # Note that here I'm using httpS <<---- "S" and that I've started an
        # HTTP server. We should get an exception
        url = URL(f"https://127.0.0.1:{http_daemon.get_port()}/")

        self.assertRaises(HTTPRequestException, self.uri_opener.GET, url)

    def test_ssl_fail_when_requesting_http_server(self):
        """
        https://github.com/andresriancho/w3af/issues/7989
        """
        # Note that here I'm using httpS <<---- "S" and that I'm connecting to
        # the net location (host:port) of an HTTP server.
        test_url = URL(f"https://127.0.0.1:{self.server.port}/")

        self.uri_opener.settings.set_max_http_retries(0)

        self.assertRaises(
            HTTPRequestException, self.uri_opener.GET, test_url, timeout=1
        )

    def test_stop(self):
        self.uri_opener.stop()
        url = URL(self.server.url())
        self.assertRaises(ScanMustStopByUserRequest, self.uri_opener.GET, url)

    def test_pause_stop(self):
        self.uri_opener.pause(True)
        self.uri_opener.stop()
        url = URL(self.server.url())
        self.assertRaises(ScanMustStopByUserRequest, self.uri_opener.GET, url)

    def _send_in_thread(self):
        output = queue.Queue()
        url = URL(self.server.url())

        def send():
            try:
                output.put(self.uri_opener.GET(url))
            except (BaseFrameworkException, ScanMustStopException):
                output.put(None)

        th = Process(target=send)
        th.daemon = True
        th.start()
        return th, output

    def test_pause(self):
        self.uri_opener.pause(True)

        th, output = self._send_in_thread()
        self.addCleanup(self.uri_opener.pause, False)
        self.addCleanup(th.join, 5)
        self.addCleanup(self.uri_opener.stop)

        self.assertRaises(queue.Empty, output.get, True, 2)
        self.assertEqual(self.server.requests, [])

    def test_pause_unpause(self):
        self.uri_opener.pause(True)

        th, output = self._send_in_thread()

        self.assertRaises(queue.Empty, output.get, True, 2)

        self.uri_opener.pause(False)

        http_response = output.get(timeout=30)
        th.join()

        self.assertIsNotNone(http_response, "Error in send thread.")
        self.assertEqual(http_response.get_code(), 200)
        self.assertIn(INDEX, http_response.body)

    def test_removes_cache(self):
        self.uri_opener.GET(URL(self.server.url()), cache=False)

        # Please note that this line, together with the cleanup act as
        # a test for a "double call to end()".
        self.uri_opener.end()

        db_fmt = "db_unittest-%s"
        trace_fmt = "db_unittest-%s_traces/"
        temp_dir = get_temp_dir()

        for i in range(100):
            test_db_path = os.path.join(temp_dir, db_fmt % i)
            test_trace_path = os.path.join(temp_dir, trace_fmt % i)
            self.assertFalse(os.path.exists(test_db_path), test_db_path)
            self.assertFalse(os.path.exists(test_trace_path), test_trace_path)

    def test_special_char_header(self):
        header_content = "name=ábc"
        headers = Headers([("Cookie", header_content)])

        url = URL(self.server.url("/echo"))
        self.uri_opener.GET(url, cache=False, headers=headers)

        # http.server decodes header bytes as latin-1, the client sent UTF-8
        wire_value = self.server.requests[-1].headers["Cookie"].encode("latin-1")
        self.assertEqual(wire_value, header_content.encode("utf-8"))

    def test_bad_file_descriptor_8125_local(self):
        """
        8125 is basically an issue with the way HTTP SSL connections handle the
        Connection: Close header.

        :see: https://github.com/andresriancho/w3af/issues/8125
        """
        raw_http_response = (
            "HTTP/1.1 200 Ok\r\n"
            "Connection: close\r\n"
            "Content-Type: text/html\r\n"
            "Content-Length: 3\r\n\r\nabc"
        )
        certfile = os.path.join(
            ROOT_PATH, "plugins", "tests", "audit", "certs", "invalid_cert.pem"
        )
        port = get_unused_port()

        s = SSLServer("localhost", port, certfile, http_response=raw_http_response)
        s.start()

        url = URL(f"https://localhost:{port}/")
        http_response = self.uri_opener.GET(url, cache=False)

        self.assertEqual("abc", http_response.body)
        s.stop()

        self.assertEqual(s.errors, [])

    def test_rate_limit_high(self):
        self.rate_limit_generic(500, 0.002)

    def test_rate_limit_low(self):
        self.rate_limit_generic(1, 1)

    def test_rate_limit_zero(self):
        self.rate_limit_generic(0, 0)

    def rate_limit_generic(self, max_requests_per_second, min_elapsed):
        url = URL(self.server.url())
        self.uri_opener.settings.set_max_requests_per_second(max_requests_per_second)

        start_time = time.monotonic()

        self.uri_opener.GET(url, cache=False)
        self.uri_opener.GET(url, cache=False)

        elapsed_time = time.monotonic() - start_time
        self.assertGreaterEqual(elapsed_time, min_elapsed)
        self.assertEqual(len(self.server.requests), 2)


cf = Config()
