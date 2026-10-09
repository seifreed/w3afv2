"""
test_proxy.py

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

import gzip
import os
import shutil
import ssl
import tempfile
import unittest
import urllib.error
import urllib.request

from w3af import ROOT_PATH
from w3af.core.controllers.daemons.proxy import Proxy, ProxyHandler
from w3af.core.controllers.exceptions import ProxyException
from w3af.core.controllers.tests.local_http_server import LocalHTTPServer, Reply
from w3af.core.data.url.extended_urllib import ExtendedUrllib
from w3af.core.filesystem import create_temp_dir

IP = "127.0.0.1"
INDEX_BODY = "<html><head><title>local proxy test</title></head></html>"
GZIP_BODY = "gzip encoded body"
HELPERS_PATH = os.path.join(ROOT_PATH, "core", "data", "url", "tests", "helpers")
TLS_CERT_AND_KEY = (
    os.path.join(HELPERS_PATH, "unittest.crt"),
    os.path.join(HELPERS_PATH, "unittest.key"),
)


def upstream_responder(_method, path):
    if path == "/gzip":
        return Reply(
            body=gzip.compress(GZIP_BODY.encode("utf-8")),
            headers={"Content-Encoding": "gzip"},
        )
    return Reply(body=INDEX_BODY)


def unverified_context():
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context


def comparable_headers(response):
    headers = {name.lower(): value for name, value in response.info().items()}
    for name in ("date", "content-encoding", "content-length", "transfer-encoding"):
        headers.pop(name, None)
    return headers


def temp_ca_dir(test_case):
    ca_dir = tempfile.mkdtemp()
    test_case.addCleanup(shutil.rmtree, ca_dir)
    return ca_dir


class TestProxy(unittest.TestCase):

    def setUp(self):
        create_temp_dir()

        self.upstream = LocalHTTPServer(upstream_responder).start()
        self.addCleanup(self.upstream.close)

        self.tls_upstream = LocalHTTPServer(
            upstream_responder, tls_cert_and_key=TLS_CERT_AND_KEY
        ).start()
        self.addCleanup(self.tls_upstream.close)

        self._proxy = Proxy(
            IP, 0, ExtendedUrllib(), ProxyHandler, ca_certs=temp_ca_dir(self)
        )
        self._proxy.start()
        self._proxy.wait_for_start()
        self.addCleanup(self._proxy.join, 5)
        self.addCleanup(self._proxy.stop)

        proxy_url = f"http://{IP}:{self._proxy.get_port()}"
        self.proxy_opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({"http": proxy_url, "https": proxy_url}),
            urllib.request.HTTPSHandler(context=unverified_context()),
        )

    def assert_same_as_direct(self, url, context=None):
        proxy_resp = self.proxy_opener.open(url)
        direct_resp = urllib.request.urlopen(url, context=context)

        self.assertEqual(direct_resp.read(), proxy_resp.read())
        self.assertEqual(
            comparable_headers(direct_resp), comparable_headers(proxy_resp)
        )
        self.assertEqual(proxy_resp.headers["content-encoding"], "identity")

    def test_do_req_through_proxy(self):
        self.assert_same_as_direct(self.upstream.url())
        self.assertEqual(self._proxy.total_handled_requests, 1)

    def test_do_ssl_req_through_proxy(self):
        self.assert_same_as_direct(self.tls_upstream.url(), unverified_context())

    def test_bind_address_and_state(self):
        self.assertEqual(self._proxy.get_bind_ip(), IP)
        self.assertEqual(self._proxy.get_bind_port(), self._proxy.get_port())
        self.assertNotEqual(self._proxy.get_port(), 0)
        self.assertTrue(self._proxy.is_running())
        self.assertEqual(self._proxy.name, "ProxyThread")

    def test_stop_no_requests(self):
        self._proxy.stop()
        self._proxy.join(5)

        self.assertFalse(self._proxy.is_running())

    def test_stop_stop(self):
        self._proxy.stop()
        self._proxy.join(5)
        self._proxy.stop()

        self.assertFalse(self._proxy.is_running())

    def test_error_handling(self):
        del self._proxy._handler.uri_opener

        with self.assertRaises(urllib.error.HTTPError) as error:
            self.proxy_opener.open(self.upstream.url())

        self.assertEqual(error.exception.code, 500)

        body = error.exception.read().decode("utf-8")
        self.assertIn("Proxy error", body)
        self.assertIn("HTTP request", body)
        self.assertIn(f"GET {self.upstream.url()} HTTP/1.1", body)
        self.assertIn("Traceback", body)

    def test_proxy_gzip_encoding(self):
        """
        The ExtendedUrllib decodes gzip encoded bodies, the proxy must change
        the content-encoding header to reflect that the body is not encoded
        anymore, otherwise the HTTP client fails to decode it.
        """
        resp = self.proxy_opener.open(self.upstream.url("/gzip"))

        self.assertEqual(resp.read().decode("utf-8"), GZIP_BODY)
        self.assertEqual(resp.headers["content-encoding"], "identity")


class TestProxyStartup(unittest.TestCase):

    def test_wait_for_start_times_out(self):
        proxy = Proxy(IP, 0, ExtendedUrllib())

        with self.assertRaisesRegex(ProxyException, "Timed out"):
            proxy.wait_for_start(timeout=0.01)

    def test_address_in_use(self):
        with LocalHTTPServer(upstream_responder) as upstream:
            proxy = Proxy(
                IP, upstream.port, ExtendedUrllib(), ca_certs=temp_ca_dir(self)
            )
            proxy.start()

            with self.assertRaisesRegex(ProxyException, "failed to start"):
                proxy.wait_for_start()

            proxy.join(5)
            proxy.stop()

        self.assertFalse(proxy.is_running())
