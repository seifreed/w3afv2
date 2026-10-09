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

"""

import base64
import unittest
from typing import ClassVar

import pytest
from clamav_client.clamd import ClamdError, ClamdNetworkSocket, ClamdUnixSocket

import w3af.core.data.kb.knowledge_base as kb
from w3af.core.controllers.threads.threadpool import Pool
from w3af.core.data.dc.headers import Headers
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.request.fuzzable_request import FuzzableRequest
from w3af.core.data.url.http_response import HTTPResponse
from w3af.plugins.grep.clamav import ScanResult, clamav
from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest

# The EICAR anti-malware test string, stored base64 encoded so this test file
# itself never contains the literal signature (which would trip host AV).
EICAR = base64.b64decode(
    "WDVPIVAlQEFQWzRcUFpYNTQoUF4pN0NDKTd9JEVJQ0FSLVNUQU5EQVJELUFOVElWSVJVUy1URVNU"
    "LUZJTEUhJEgrSCo="
).decode("latin-1")


def _clamd_available():
    candidates = [
        "/var/run/clamav/clamd.ctl",
        "/opt/homebrew/var/run/clamav/clamd.sock",
        "/tmp/clamd.socket",
    ]
    for path in candidates:
        try:
            if ClamdUnixSocket(path).ping():
                return True
        except (ClamdError, OSError):
            continue
    try:
        return bool(ClamdNetworkSocket("127.0.0.1", 3310).ping())
    except (ClamdError, OSError):
        return False


CLAMD_AVAILABLE = _clamd_available()
CLAMD_REASON = "The ClamAV clamd daemon is not running"


class TestClamAV(unittest.TestCase):

    def setUp(self):
        pool = Pool(3)

        self.plugin = clamav()
        self.plugin.set_worker_pool(pool)

        kb.kb.clear("clamav", "malware")

    def tearDown(self):
        self.plugin.end()

    @pytest.mark.skipif(not CLAMD_AVAILABLE, reason=CLAMD_REASON)
    def test_clamav_eicar(self):
        body = EICAR
        url = URL("http://www.w3af.com/")
        headers = Headers([("content-type", "text/html")])
        response = HTTPResponse(200, body, headers, url, url, _id=1)
        request = FuzzableRequest(url, method="GET")

        self.plugin.grep(request, response)

        # Let the worker pool wait for the clamd response, this is done by
        # the core when run in a real scan
        self.plugin.worker_pool.close()
        self.plugin.worker_pool.join()

        findings = kb.kb.get("clamav", "malware")

        self.assertEqual(len(findings), 1)
        finding = findings[0]

        self.assertEqual(finding.get_name(), "Malware identified")
        self.assertIn("ClamAV identified malware", finding.get_desc())
        self.assertEqual(finding.get_url().url_string, url.url_string)

    def test_clamav_empty(self):
        body = ""
        url = URL("http://www.w3af.com/")
        headers = Headers([("content-type", "text/html")])
        response = HTTPResponse(200, body, headers, url, url, _id=1)
        request = FuzzableRequest(url, method="GET")

        self.plugin.grep(request, response)

        # Let the worker pool wait for the clamd response, this is done by
        # the core when run in a real scan
        self.plugin.worker_pool.close()
        self.plugin.worker_pool.join()

        findings = kb.kb.get("clamav", "malware")

        self.assertEqual(len(findings), 0, findings)

    def test_unavailable_clamd_skips_scanning(self):
        body = "test body"
        url = URL("http://www.w3af.com/")
        headers = Headers([("content-type", "text/html")])
        response = HTTPResponse(200, body, headers, url, url, _id=1)
        request = FuzzableRequest(url, method="GET")

        self.plugin._clamd_socket = "tcp://127.0.0.1:0"
        self.plugin.grep(request, response)
        findings = kb.kb.get("clamav", "malware")

        self.assertEqual(len(findings), 0)
        self.assertFalse(self.plugin._properly_configured)

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


@pytest.mark.skipif(not CLAMD_AVAILABLE, reason=CLAMD_REASON)
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

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse("http://mock/grep/clamav/", body=INDEX, method="GET"),
        MockResponse("http://mock/grep/clamav/eicar.com.txt", body=EICAR),
        MockResponse("http://mock/grep/clamav/eicar.com", body=EICAR),
        MockResponse("http://mock/grep/clamav/eicarcom2.zip", body=EICAR),
        MockResponse("http://mock/grep/clamav/eicar_com.zip", body=EICAR),
    ]

    _run_configs: ClassVar[dict] = {
        "cfg": {
            "target": target_url,
            "plugins": {
                "grep": (PluginConfig("clamav"),),
                "crawl": (
                    PluginConfig(
                        "web_spider", ("only_forward", True, PluginConfig.BOOL)
                    ),
                ),
            },
        },
    }

    def setUp(self):
        self.plugin = clamav()
        super().setUp()

    def tearDown(self):
        super().tearDown()
        self.plugin.end()

    def test_found_vuln(self):
        """
        Test to validate case in which malware is identified while crawling.
        """
        # Configure and run test case
        cfg = self._run_configs["cfg"]
        self._scan(cfg["target"], cfg["plugins"])

        findings = kb.kb.get("clamav", "malware")

        self.assertEqual(len(findings), 4)

        EXPECTED_FILES = (
            "eicar.com.txt",
            "eicar.com",
            "eicarcom2.zip",
            "eicar_com.zip",
        )

        for finding in findings:
            self.assertIn(finding.get_url().get_file_name(), EXPECTED_FILES)
            self.assertEqual(finding.get_name(), "Malware identified")
            self.assertIn("ClamAV identified malware", finding.get_desc())
