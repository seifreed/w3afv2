"""
test_intercept_proxy.py

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

import queue
import shutil
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
import urllib.response

import w3af.core.controllers.output_manager as om
from w3af.core.controllers.daemons.proxy import InterceptProxy
from w3af.core.controllers.tests.local_http_server import LocalHTTPServer, Reply
from w3af.core.data.url.extended_urllib import ExtendedUrllib
from w3af.core.exceptions import ProxyException
from w3af.core.filesystem import create_temp_dir

IP = "127.0.0.1"
INDEX_TITLE = "<title>local vulnerable web application</title>"
PAGE_NOT_FOUND = "Page not found"
POST_RECEIVED = "POST received"
WAIT_SECONDS = 10


def _upstream_responder(method, path):
    if method == "POST":
        return Reply(status=200, body=POST_RECEIVED)
    if path in ("/", "/style.css"):
        return Reply(status=200, body=f"<html><head>{INDEX_TITLE}</head></html>")
    return Reply(status=404, body=PAGE_NOT_FOUND)


class TestInterceptProxy(unittest.TestCase):

    def setUp(self):
        create_temp_dir()

        self._upstream = LocalHTTPServer(_upstream_responder).start()
        self.addCleanup(self._upstream.close)

        ca_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, ca_dir)

        self._proxy = InterceptProxy(IP, 0, ExtendedUrllib(), om.out, ca_certs=ca_dir)
        self._proxy.start()
        self._proxy.wait_for_start()
        self.addCleanup(self._proxy.join, 5)
        self.addCleanup(self._proxy.stop)

        proxy_url = f"http://{IP}:{self._proxy.get_port()}"
        self.proxy_opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({"http": proxy_url, "https": proxy_url})
        )

    def upstream_url(self, path="/"):
        return self._upstream.url(path)

    def send_in_background(self, url):
        """
        Send a request through the proxy from another thread, the response (or
        the HTTPError) is put in the returned queue.
        """
        results: queue.Queue[urllib.response.addinfourl | urllib.error.HTTPError] = (
            queue.Queue()
        )

        def send_request():
            try:
                results.put(self.proxy_opener.open(url, timeout=WAIT_SECONDS))
            except urllib.error.HTTPError as http_error:
                results.put(http_error)

        threading.Thread(target=send_request, daemon=True).start()
        return results

    def wait_for_trapped_request(self):
        deadline = time.monotonic() + WAIT_SECONDS
        while time.monotonic() < deadline:
            request = self._proxy.get_trapped_request()
            if request is not None:
                return request
            time.sleep(0.05)
        self.fail("The proxy did not trap the request")

    def trap_request(self, path="/"):
        self._proxy.set_trap(True)
        results = self.send_in_background(self.upstream_url(path))
        request = self.wait_for_trapped_request()

        self.assertEqual(request.get_uri().url_string, self.upstream_url(path))
        self.assertEqual(request.get_method(), "GET")
        return request, results

    def assert_not_trapped(self, url):
        response = self.proxy_opener.open(url, timeout=WAIT_SECONDS)

        self.assertEqual(response.code, 200)
        self.assertIsNone(self._proxy.get_trapped_request())

    def test_get_thread_name(self):
        self.assertEqual(self._proxy.name, "LocalProxyThread")

    def test_no_request(self):
        self.assertIsNone(self._proxy.get_trapped_request())

    def test_no_trap(self):
        self._proxy.set_trap(False)
        response = self.proxy_opener.open(self.upstream_url())

        self.assertFalse(self._proxy.get_trap())
        self.assertIn(INDEX_TITLE, response.read().decode("utf-8"))
        self.assertEqual(response.code, 200)

    def test_request_trapped_drop(self):
        request, results = self.trap_request()

        self._proxy.drop_request(request)

        response = results.get(timeout=WAIT_SECONDS)
        self.assertEqual(response.code, 403)
        self.assertIn("HTTP request drop by user", response.read().decode("utf-8"))

    def test_request_trapped_send(self):
        request, results = self.trap_request()

        self.assertTrue(self._proxy.get_trap())
        self._proxy.on_request_edit_finished(
            request, request.dump_request_head(), request.get_data()
        )

        response = results.get(timeout=WAIT_SECONDS)
        self.assertEqual(response.code, 200)
        self.assertIn(INDEX_TITLE, response.read().decode("utf-8"))

    def test_request_trapped_edited(self):
        request, results = self.trap_request()
        edited_head = request.dump_request_head().replace(
            f"GET {self.upstream_url()} ", f"GET {self.upstream_url('/edited')} "
        )

        self._proxy.on_request_edit_finished(request, edited_head, b"")

        response = results.get(timeout=WAIT_SECONDS)
        self.assertEqual(response.code, 404)
        self.assertIn("/edited", self._upstream.requested_paths)

    def test_request_trapped_edited_to_post(self):
        request, results = self.trap_request()
        post_head = (
            f"POST {self.upstream_url('/form')} HTTP/1.1\r\n"
            f"Host: {IP}:{self._upstream.port}\r\n"
            "Content-Type: application/x-www-form-urlencoded\r\n"
        )

        http_response = self._proxy.on_request_edit_finished(
            request, post_head, b"name=value"
        )

        self.assertEqual(http_response.get_code(), 200)
        response = results.get(timeout=WAIT_SECONDS)
        self.assertEqual(response.read().decode("utf-8"), POST_RECEIVED)

    def test_request_trapped_edit_invalid(self):
        request, results = self.trap_request()

        http_response = self._proxy.on_request_edit_finished(request, "invalid", b"")

        self.assertEqual(http_response.get_code(), 500)
        response = results.get(timeout=WAIT_SECONDS)
        self.assertEqual(response.code, 500)
        body = response.read().decode("utf-8")
        self.assertIn("Proxy error", body)
        self.assertIn(f"GET {self.upstream_url()} HTTP/1.1", body)

    def test_send_error_without_trap(self):
        del self._proxy._handler.uri_opener

        with self.assertRaises(urllib.error.HTTPError) as error:
            self.proxy_opener.open(self.upstream_url(), timeout=WAIT_SECONDS)

        self.assertEqual(error.exception.code, 500)
        self.assertIn("Proxy error", error.exception.read().decode("utf-8"))

    def test_methods_to_trap(self):
        self._proxy.set_trap(True)
        self._proxy.set_methods_to_trap(["post"])

        self.assertEqual(self._proxy.methods_to_trap, {"POST"})
        self.assert_not_trapped(self.upstream_url())

    def test_what_not_to_trap(self):
        self._proxy.set_trap(True)
        self._proxy.set_what_not_to_trap(r".*\.css$")

        self.assert_not_trapped(self.upstream_url("/style.css"))

    def test_what_to_trap(self):
        self._proxy.set_trap(True)
        self._proxy.set_what_to_trap("never-matches")

        self.assert_not_trapped(self.upstream_url())

    def test_invalid_trap_regex(self):
        with self.assertRaises(ProxyException):
            self._proxy.set_what_to_trap("(")

        with self.assertRaises(ProxyException):
            self._proxy.set_what_not_to_trap("(")

    def test_trap_many(self):
        self._proxy.set_trap(True)
        pending = []

        for i in range(3):
            results = self.send_in_background(self.upstream_url(f"/{i}"))
            request = self.wait_for_trapped_request()
            self.assertEqual(request.get_uri().url_string, self.upstream_url(f"/{i}"))
            pending.append((request, results))

        (first, first_results), (second, second_results), (third, third_results) = (
            pending
        )

        self._proxy.on_request_edit_finished(
            first, first.dump_request_head(), first.get_data()
        )
        response = first_results.get(timeout=WAIT_SECONDS)
        self.assertEqual(response.geturl(), self.upstream_url("/0"))
        self.assertEqual(response.code, 404)
        self.assertIn(PAGE_NOT_FOUND, response.read().decode("utf-8"))

        self._proxy.drop_request(second)
        response = second_results.get(timeout=WAIT_SECONDS)
        self.assertEqual(response.geturl(), self.upstream_url("/1"))
        self.assertEqual(response.code, 403)

        self._proxy.on_request_edit_finished(
            third, third.dump_request_head(), third.get_data()
        )
        response = third_results.get(timeout=WAIT_SECONDS)
        self.assertEqual(response.geturl(), self.upstream_url("/2"))
        self.assertEqual(response.code, 404)
