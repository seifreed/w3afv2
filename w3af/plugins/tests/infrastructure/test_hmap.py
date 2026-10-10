"""
test_hmap.py

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
import re
import socket
import ssl
import struct
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import ClassVar

import w3af.plugins.infrastructure.oHmap.hmap as upstream_hmap
from w3af.core.controllers.tests.recording_output import recording_output
from w3af.core.exceptions import BaseFrameworkException
from w3af.plugins.infrastructure.hmap import hmap
from w3af.plugins.tests.canned_http_server import CERT_FILE, KEY_FILE
from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest

SERVER_NAME = "HmapTestSite/1.0"


class HmapTestSiteHandler(BaseHTTPRequestHandler):
    """
    A small web server which, like most real ones, waits for the request body
    announced in the Content-Length header before answering.
    """

    def version_string(self):
        return SERVER_NAME

    def log_message(self, format, *args):
        return

    def do_GET(self):
        self._read_announced_body()
        self._send(
            200,
            {"ETag": '"5f3a-hmap"', "Vary": "Accept-Encoding"},
            b"<html><body>hmap test site</body></html>",
        )

    def do_HEAD(self):
        self._send(200, {}, b"")

    def do_OPTIONS(self):
        allowed = "GET, HEAD, OPTIONS"
        self._send(200, {"Allow": allowed, "Public": allowed}, b"")

    def _read_announced_body(self):
        remaining = int(self.headers.get("Content-Length") or 0)

        while remaining > 0 and (chunk := self.rfile.read1(min(remaining, 65536))):
            remaining -= len(chunk)

    def _send(self, status, headers, body):
        self.send_response(status)
        for name, value in headers.items():
            self.send_header(name, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)


class HmapTestSite(ThreadingHTTPServer):
    """
    Serve the hmap test site on an ephemeral 127.0.0.1 port, optionally over
    TLS, since hmap connects directly to the target without using the proxy.
    """

    daemon_threads = True

    def __init__(self, use_ssl=False):
        super().__init__(("127.0.0.1", 0), HmapTestSiteHandler)
        self.tls_context = None

        if use_ssl:
            self.tls_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            self.tls_context.load_cert_chain(CERT_FILE, KEY_FILE)

        self._thread = threading.Thread(target=self.serve_forever, daemon=True)
        self._thread.start()

    @property
    def port(self):
        return self.server_address[1]

    def get_request(self):
        connection, address = super().get_request()

        if self.tls_context is not None:
            connection = self.tls_context.wrap_socket(
                connection, server_side=True, do_handshake_on_connect=False
            )

        return connection, address

    def handle_error(self, request, client_address):
        # hmap closes connections without waiting for the responses
        return

    def stop(self):
        self.shutdown()
        self.server_close()
        self._thread.join()


class ResettingServer:
    """
    Accept TCP connections and reset them right away.
    """

    def __init__(self):
        self._socket = socket.create_server(("127.0.0.1", 0))
        self.port = self._socket.getsockname()[1]
        self._thread = threading.Thread(target=self._reset_connections, daemon=True)
        self._thread.start()

    def _reset_connections(self):
        while True:
            try:
                connection, _ = self._socket.accept()
            except OSError:
                return

            linger = struct.pack("ii", 1, 0)
            connection.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, linger)
            connection.close()

    def stop(self):
        self._socket.close()
        self._thread.join()


def closed_port():
    """
    :return: A 127.0.0.1 port where nothing is listening
    """
    with socket.create_server(("127.0.0.1", 0)) as server:
        return server.getsockname()[1]


class HmapScanTest(PluginTest):
    """
    The scanner requests are answered by the canned server, while hmap sends
    its probes straight to the target host and port.
    """

    target_url = "http://127.0.0.1/"

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(re.compile(r"https?://127\.0\.0\.1:\d+/.*"), "Hello world")
    ]

    def _scan_hmap(self, target, *options):
        plugins = {"infrastructure": (PluginConfig("hmap", *options),)}
        self._scan(target, plugins)


class TestHmap(HmapScanTest):
    def setUp(self):
        super().setUp()
        self.site = HmapTestSite()
        self.addCleanup(self.site.stop)

    def _fingerprint_file(self):
        filename = os.path.abspath("hmap-fingerprint-127.0.0.1-0")
        self.addCleanup(os.remove, filename)
        return filename

    def test_hmap_http(self):
        fingerprint_file = self._fingerprint_file()

        self._scan_hmap(
            f"http://127.0.0.1:{self.site.port}/",
            ("gen_fingerprint", True, PluginConfig.BOOL),
        )

        infos = self.kb.get("hmap", "server")
        self.assertEqual(len(infos), 1, infos)

        server = infos[0]["server"]
        self.assertIn(f'"{server}"', infos[0].get_desc())
        self.assertEqual(self.kb.raw_read("hmap", "server_string"), server)

        with open(fingerprint_file) as fingerprint:
            self.assertIn(SERVER_NAME, fingerprint.read())

        semantic = upstream_hmap.fingerprint["SEMANTIC"]
        self.assertEqual(semantic["MALFORMED_000"], "400")
        self.assertEqual(semantic["MALFORMED_001"], "NO_RESPONSE_CODE")
        self.assertEqual(semantic["LONG_DEFAULT_RANGES"], [(1, "200"), (10000, "200")])

        syntactic = upstream_hmap.fingerprint["SYNTACTIC"]
        self.assertEqual(syntactic["ALLOW_ORDER"], "GET, HEAD, OPTIONS")
        self.assertEqual(syntactic["ETag"], '"5f3a-hmap"')


class TestHmapHTTPS(HmapScanTest):
    def setUp(self):
        super().setUp()
        self.site = HmapTestSite(use_ssl=True)
        self.addCleanup(self.site.stop)

    def test_hmap_https(self):
        self._scan_hmap(f"https://127.0.0.1:{self.site.port}/")

        infos = self.kb.get("hmap", "server")
        self.assertEqual(len(infos), 1, infos)
        self.assertEqual(
            upstream_hmap.fingerprint["LEXICAL"]["SERVER_NAME"], SERVER_NAME
        )


class TestHmapUnreachableServer(HmapScanTest):
    def test_connection_refused(self):
        self._scan_hmap(f"http://127.0.0.1:{closed_port()}/")

        self.assertEqual(self.kb.get("hmap", "server"), [])


class TestHmapPlugin(unittest.TestCase):
    def test_options_round_trip(self):
        plugin = hmap()
        options = plugin.get_options()
        options["gen_fingerprint"].set_value(True)
        options["threads"].set_value(2)

        plugin.set_options(options)

        self.assertTrue(plugin.get_options()["gen_fingerprint"].get_value())
        self.assertEqual(plugin.get_options()["threads"].get_value(), 2)

    def test_dependencies_and_description(self):
        plugin = hmap()

        self.assertEqual(plugin.get_plugin_deps(), ["infrastructure.server_header"])
        self.assertIn("Dustin Lee's hmap", plugin.get_long_desc())


class TestHmapConnections(unittest.TestCase):
    def setUp(self):
        self.output = recording_output()

    def test_connection_refused(self):
        target = upstream_hmap.Target("127.0.0.1", closed_port(), False, self.output)

        with self.assertRaises(BaseFrameworkException):
            upstream_hmap.request(target).submit()

    def test_ssl_handshake_with_plain_http_server(self):
        site = HmapTestSite()
        self.addCleanup(site.stop)
        target = upstream_hmap.Target("127.0.0.1", site.port, True, self.output)

        with self.assertRaisesRegex(BaseFrameworkException, "SSL connection failed"):
            upstream_hmap.request(target).get_connection()

    def test_reset_connections_give_an_empty_response(self):
        server = ResettingServer()
        self.addCleanup(server.stop)
        target = upstream_hmap.Target("127.0.0.1", server.port, False, self.output)

        res = upstream_hmap.request(target).submit()

        self.assertEqual(res.return_code(), ("NO_RESPONSE", "NONE"))


class TestHmapResponse(unittest.TestCase):
    def test_lf_separated_response(self):
        res = upstream_hmap.response("HTTP/1.0 200 OK\nServer: lf\n\nbody")

        self.assertEqual(res.return_code(), ("200", "OK"))
        self.assertEqual(res.header_names(), ["Server"])
        self.assertEqual(res.servername(), "lf")
        self.assertEqual(res.body, ["", "body"])

    def test_response_without_blank_line(self):
        res = upstream_hmap.response("HTTP/1.1 302 Found\r\nLocation: /")

        self.assertEqual(res.return_code(), ("302", "Found"))
        self.assertEqual(res.header_data("location"), "/")
        self.assertIsNone(res.header_data("Server"))
        self.assertEqual(res.body, [])

    def test_response_without_status_line(self):
        res = upstream_hmap.response("<html>HTTP/0.9 like</html>")

        self.assertEqual(res.return_code(), ("NO_RESPONSE_CODE", "NONE"))
        self.assertEqual(res.body, "<html>HTTP/0.9 like</html>")


class TestHmapFingerprint(unittest.TestCase):
    def setUp(self):
        for characteristics in upstream_hmap.fingerprint.values():
            characteristics.clear()

    def test_add_characteristic_collects_different_values(self):
        upstream_hmap.add_characteristic("LEXICAL", "404", "Not Found")
        upstream_hmap.add_characteristic("LEXICAL", "404", "Not Found")
        upstream_hmap.add_characteristic("LEXICAL", "404", "File Not Found")
        upstream_hmap.add_characteristic("LEXICAL", "404", "Missing")
        upstream_hmap.add_characteristic("LEXICAL", "404", "Missing")

        self.assertEqual(
            upstream_hmap.fingerprint["LEXICAL"]["404"],
            ["Not Found", "File Not Found", "Missing"],
        )

    def test_no_response_has_no_header_order(self):
        upstream_hmap.get_characteristics("basic_get", upstream_hmap.response(""))

        self.assertEqual(upstream_hmap.fingerprint["LEXICAL"], {})
        self.assertEqual(upstream_hmap.fingerprint["SYNTACTIC"], {"HEADER_ORDER": [[]]})

    def test_winnow_ordered_list(self):
        self.assertEqual(upstream_hmap.winnow_ordered_list([["Date"]]), [["Date"]])
        self.assertEqual(
            upstream_hmap.winnow_ordered_list(
                [["Date", "Server", "Allow"], ["Server", "Date"], ["Date", "Allow"]]
            ),
            [["Server", "Date"], ["Date", "Server", "Allow"]],
        )

    def test_is_partial_ordered_sublist(self):
        sublist = upstream_hmap.is_partial_ordered_sublist

        self.assertTrue(sublist(["Date", "Allow"], ["Date", "Server", "Allow"]))
        self.assertFalse(sublist(["Allow", "Date"], ["Date", "Server", "Allow"]))
        self.assertFalse(sublist(["Date", "ETag"], ["Date", "Server", "Allow"]))
        self.assertFalse(sublist(["Date", "Server", "Allow"], ["Date"]))

    def test_find_halfways_skips_adjacent_sizes(self):
        ranges = [(1, "200"), (2, "414"), (10, "414"), (20, "400")]

        self.assertEqual(upstream_hmap.find_halfways(ranges), [15])
        self.assertEqual(
            upstream_hmap.minimize_ranges(ranges),
            [(1, "200"), (2, "414"), (10, "414"), (20, "400")],
        )


class TestHmapComparison(unittest.TestCase):
    def _fingerprint(self, lexical, allow_order):
        semantic = dict.fromkeys(upstream_hmap.SEMANTIC_NAMES, "400")
        syntactic = {"ALLOW_ORDER": allow_order} if allow_order else {}
        return {"LEXICAL": lexical, "SYNTACTIC": syntactic, "SEMANTIC": semantic}

    def test_compare_fingerprints(self):
        known = self._fingerprint({"200": "OK", "404": "Not Found"}, "GET, HEAD")
        subject = self._fingerprint({"200": "OK", "404": "Missing"}, "GET, HEAD")
        subject["SEMANTIC"].pop("LONG_URL_RANGES")

        matches, mismatches, unknowns = upstream_hmap.compare_fingerprints(
            known, subject
        )

        semantic_count = len(upstream_hmap.SEMANTIC_NAMES)
        self.assertEqual(matches, 1 + 1 + semantic_count - 1)
        self.assertEqual(mismatches, 1 + 1)
        self.assertEqual(unknowns, len(upstream_hmap.LEXICAL_CODES) - 2)

    def test_compare_allow_orders(self):
        known = self._fingerprint({}, "GET, HEAD")

        _, mismatches, _ = upstream_hmap.compare_fingerprints(
            known, self._fingerprint({}, "HEAD, GET")
        )
        _, _, unknowns = upstream_hmap.compare_fingerprints(
            known, self._fingerprint({}, "")
        )

        self.assertEqual(mismatches, 1)
        self.assertEqual(unknowns, len(upstream_hmap.LEXICAL_CODES) + 1)


class TestHmapFiles(unittest.TestCase):
    def test_invalid_signature_file(self):
        with tempfile.TemporaryDirectory() as fingerprint_dir:
            signature = os.path.join(fingerprint_dir, "broken-server")
            with open(signature, "w") as signature_file:
                signature_file.write("{'LEXICAL': ")

            with self.assertRaisesRegex(BaseFrameworkException, "invalid syntax"):
                upstream_hmap.load_known_servers(fingerprint_dir)

    def test_known_servers_are_loaded(self):
        known_servers = upstream_hmap.load_known_servers(
            upstream_hmap.KNOWN_SERVERS_DIR
        )

        self.assertGreater(len(known_servers), 50)

    def test_unwritable_fingerprint_file(self):
        with self.assertRaisesRegex(BaseFrameworkException, "Cannot open"):
            upstream_hmap.write_fingerprint_file({}, "missing-dir/127.0.0.1")
