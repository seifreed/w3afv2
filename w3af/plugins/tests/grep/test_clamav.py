"""
test_clamav.py

Copyright 2013 Andres Riancho

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

clamd is replaced by LocalClamd, a real TCP / Unix socket server speaking the
subset of the clamd protocol used by the plugin (PING, VERSION, INSTREAM).
"""

import base64
import os
import shutil
import socketserver
import struct
import tempfile
import threading
import unittest
from typing import ClassVar

from clamav_client.clamd import ClamdNetworkSocket, ClamdUnixSocket

import w3af.core.data.kb.knowledge_base as kb
from w3af.core.controllers.threads.threadpool import Pool
from w3af.plugins.grep.clamav import ScanResult, clamav
from w3af.plugins.tests.grep.grep_test_utils import make_request, make_response
from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest

# The EICAR anti-malware test string, stored base64 encoded so this test file
# itself never contains the literal signature (which would trip host AV).
EICAR = base64.b64decode(
    "WDVPIVAlQEFQWzRcUFpYNTQoUF4pN0NDKTd9JEVJQ0FSLVNUQU5EQVJELUFOVElWSVJVUy1URVNU"
    "LUZJTEUhJEgrSCo="
).decode("latin-1")

CLAMD_VERSION = "ClamAV 1.4.1/27411/Mon Oct  6 08:00:00 2026"


class ClamdHandler(socketserver.StreamRequestHandler):
    """
    Answers one clamd command per connection, like clamd does for commands
    prefixed with "n" which are not sent inside an IDSESSION.
    """

    def handle(self):
        command = self.rfile.readline().decode().strip()
        replies = self.server.replies

        if command == "nPING":
            self.reply(replies.get("PING", "PONG"))
        elif command == "nVERSION":
            self.reply(CLAMD_VERSION)
        elif command == "nINSTREAM":
            result = self.scan(self.read_stream())
            reply = replies.get("INSTREAM", result)
            if reply:
                self.reply(reply)

    def read_stream(self):
        chunks = []
        while size := struct.unpack("!L", self.rfile.read(4))[0]:
            chunks.append(self.rfile.read(size))
        return b"".join(chunks)

    @staticmethod
    def scan(data):
        if EICAR.encode("latin-1") in data:
            return "stream: Eicar-Test-Signature FOUND"
        return "stream: OK"

    def reply(self, line):
        self.wfile.write(f"{line}\n".encode())


class LocalClamd:
    """
    :param unix_socket: Listen on this Unix socket path instead of on a TCP
                        port bound to 127.0.0.1.
    :param replies: Fixed answers per command, used to simulate broken
                    daemons. An empty INSTREAM reply closes the connection
                    without answering.
    """

    def __init__(self, unix_socket=None, **replies):
        if unix_socket is None:
            self.server = socketserver.ThreadingTCPServer(
                ("127.0.0.1", 0), ClamdHandler
            )
            self.endpoint = f"tcp://127.0.0.1:{self.server.server_address[1]}"
        else:
            self.server = socketserver.ThreadingUnixStreamServer(
                unix_socket, ClamdHandler
            )
            self.endpoint = unix_socket

        self.server.daemon_threads = True
        self.server.replies = replies
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc_info):
        self.server.shutdown()
        self.server.server_close()


class ClamAVTestCase(unittest.TestCase):

    def setUp(self):
        kb.kb.clear("clamav", "malware")
        self.pool = Pool(3)
        self.addCleanup(self.pool.terminate_join)

    def start_clamd(self, unix_socket=None, **replies):
        clamd = LocalClamd(unix_socket, **replies)
        self.enterContext(clamd)
        return clamd

    def make_plugin(self, endpoint):
        plugin = clamav()
        options = plugin.get_options()
        options["clamd_socket"].set_value(endpoint)
        plugin.set_options(options)
        plugin.set_worker_pool(self.pool)
        return plugin

    def grep(self, plugin, body, method="GET", code=200):
        url = "http://www.w3af.com/"
        plugin.grep(make_request(url, method=method), make_response(url, body, code))

        # Let the worker pool wait for the clamd response, this is done by
        # the core when run in a real scan
        self.pool.close()
        self.pool.join()

        return kb.kb.get("clamav", "malware")


class TestClamAV(ClamAVTestCase):

    def test_clamav_eicar(self):
        plugin = self.make_plugin(self.start_clamd().endpoint)

        findings = self.grep(plugin, EICAR)

        self.assertEqual(len(findings), 1)
        finding = findings[0]

        self.assertEqual(finding.get_name(), "Malware identified")
        self.assertIn("ClamAV identified malware", finding.get_desc())
        self.assertIn("Eicar-Test-Signature", finding.get_desc())
        self.assertEqual(finding.get_url().url_string, "http://www.w3af.com/")

    def test_clamav_empty(self):
        plugin = self.make_plugin(self.start_clamd().endpoint)

        findings = self.grep(plugin, "")

        self.assertEqual(len(findings), 0, findings)
        self.assertTrue(plugin._properly_configured)

    def test_unix_socket(self):
        directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, directory)
        clamd = self.start_clamd(unix_socket=os.path.join(directory, "clamd.sock"))

        plugin = self.make_plugin(clamd.endpoint)

        self.assertEqual(len(self.grep(plugin, EICAR)), 1)

    def test_ignored_requests_and_responses(self):
        plugin = self.make_plugin(self.start_clamd().endpoint)

        self.assertEqual(self.grep(plugin, EICAR, method="POST"), [])
        self.assertEqual(self.grep(plugin, EICAR, code=404), [])
        self.assertTrue(plugin._properly_configured)

    def test_unavailable_clamd_skips_scanning(self):
        plugin = self.make_plugin("tcp://127.0.0.1:0")

        self.assertEqual(self.grep(plugin, "test body"), [])
        self.assertFalse(plugin._properly_configured)

    def test_unexpected_ping_reply(self):
        plugin = self.make_plugin(self.start_clamd(PING="PANG").endpoint)

        self.assertEqual(self.grep(plugin, EICAR), [])
        self.assertFalse(plugin._properly_configured)

    def test_scan_error_disables_plugin(self):
        clamd = self.start_clamd(INSTREAM="INSTREAM size limit exceeded. ERROR")
        plugin = self.make_plugin(clamd.endpoint)

        self.assertEqual(self.grep(plugin, EICAR), [])
        self.assertFalse(plugin._properly_configured)

    def test_empty_scan_reply_is_ignored(self):
        plugin = self.make_plugin(self.start_clamd(INSTREAM="").endpoint)

        self.assertEqual(self.grep(plugin, EICAR), [])
        self.assertTrue(plugin._properly_configured)

    def test_options(self):
        plugin = self.make_plugin("tcp://clamd.local:3311")

        self.assertEqual(
            plugin.get_options()["clamd_socket"].get_value(), "tcp://clamd.local:3311"
        )
        self.assertIn("ClamAV", plugin.get_long_desc())


class TestClamAVConnection(unittest.TestCase):

    def setUp(self):
        self.plugin = clamav()

    def test_connection_supports_unix_and_tcp_endpoints(self):
        self.assertIsInstance(self.plugin._get_connection(), ClamdUnixSocket)

        self.plugin._clamd_socket = "tcp://127.0.0.1:3311"
        connection = self.plugin._get_connection()

        self.assertIsInstance(connection, ClamdNetworkSocket)
        self.assertEqual(connection.host, "127.0.0.1")
        self.assertEqual(connection.port, 3311)

    def test_connection_uses_default_tcp_port(self):
        self.plugin._clamd_socket = "tcp://localhost"

        connection = self.plugin._get_connection()

        self.assertIsInstance(connection, ClamdNetworkSocket)
        self.assertEqual(connection.port, 3310)

    def test_connection_rejects_invalid_tcp_endpoint(self):
        self.plugin._clamd_socket = "tcp:///clamd"

        with self.assertRaises(ValueError):
            self.plugin._get_connection()

    def test_parse_scan_result(self):
        found = self.plugin._parse_scan_result(
            {"stream": ("FOUND", "Eicar-Test-Signature")}
        )
        clean = self.plugin._parse_scan_result({"stream": ("OK", None)})

        self.assertEqual(found, ScanResult(True, "Eicar-Test-Signature"))
        self.assertEqual(clean, ScanResult(False, None))


class TestClamAVScan(PluginTest):

    target_url = "http://mock/grep/clamav/"

    INDEX = (
        "<html><body>"
        '<a href="eicar.com.txt">1</a>'
        '<a href="eicar.com">2</a>'
        '<a href="eicarcom2.zip">3</a>'
        '<a href="eicar_com.zip">4</a>'
        "</body></html>"
    )

    # The grep consumer analyzes identical bodies only once. EICAR allows
    # trailing whitespace, which makes each file unique.
    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse("http://mock/grep/clamav/", body=INDEX, method="GET"),
        MockResponse("http://mock/grep/clamav/eicar.com.txt", body=EICAR),
        MockResponse("http://mock/grep/clamav/eicar.com", body=EICAR + "\n"),
        MockResponse("http://mock/grep/clamav/eicarcom2.zip", body=EICAR + "\n\n"),
        MockResponse("http://mock/grep/clamav/eicar_com.zip", body=EICAR + " "),
    ]

    def test_found_vuln(self):
        """
        Test to validate case in which malware is identified while crawling.
        """
        clamd = LocalClamd()
        self.enterContext(clamd)

        plugins = {
            "grep": (
                PluginConfig(
                    "clamav", ("clamd_socket", clamd.endpoint, PluginConfig.STR)
                ),
            ),
            "crawl": (
                PluginConfig("web_spider", ("only_forward", True, PluginConfig.BOOL)),
            ),
        }
        self._scan(self.target_url, plugins)

        findings = kb.kb.get("clamav", "malware")

        self.assertEqual(len(findings), 4)

        expected_files = (
            "eicar.com.txt",
            "eicar.com",
            "eicarcom2.zip",
            "eicar_com.zip",
        )

        for finding in findings:
            self.assertIn(finding.get_url().get_file_name(), expected_files)
            self.assertEqual(finding.get_name(), "Malware identified")
            self.assertIn("ClamAV identified malware", finding.get_desc())
