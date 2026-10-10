"""
test_fingerprint_waf.py

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

import unittest
from typing import ClassVar

from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.request.fuzzable_request import FuzzableRequest
from w3af.plugins.infrastructure.fingerprint_waf import fingerprint_waf
from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest


class WAFTest:
    domain = "httpretty-mock"
    target_url: str | None = f"http://{domain}/"

    _run_configs: ClassVar[dict] = {
        "cfg": {
            "target": target_url,
            "plugins": {"infrastructure": (PluginConfig("fingerprint_waf"),)},
        }
    }


class TestFingerprintWAFIBMWebSphere(WAFTest, PluginTest):

    IBM_WAF = "X-Backside-Transport=1"
    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(WAFTest.target_url, "Hello world", headers={"Set-Cookie": IBM_WAF})
    ]

    def test_fingerprint_waf(self):
        cfg = self._run_configs["cfg"]
        self._scan(cfg["target"], cfg["plugins"])

        infos = self.kb.get("fingerprint_waf", "IBM WebSphere")
        self.assertEqual(len(infos), 1, infos)
        info = infos[0]

        name = "Web Application Firewall fingerprint"
        desc = (
            'The remote network seems to have a "IBM WebSphere" WAF'
            " deployed to protect access to the web server. The following"
            ' is the WAF\'s version: "X-Backside-Transport=1".'
        )

        self.assertEqual(info.get_name(), name)
        self.assertEqual(info.get_desc(with_id=False), desc)
        self.assertIn(self.IBM_WAF, info.get_desc())


class TestFingerprintWAFNone(WAFTest, PluginTest):

    MOCK_RESPONSES: ClassVar[list] = [MockResponse(WAFTest.target_url, "Hello world")]

    def test_fingerprint_waf(self):
        cfg = self._run_configs["cfg"]
        self._scan(cfg["target"], cfg["plugins"])

        infos = self.kb.get("fingerprint_waf", "fingerprint_waf")
        self.assertEqual(len(infos), 0, infos)


def _waf_site(host, headers):
    return MockResponse(f"http://{host}/", "Hello world", headers=headers)


def _not_found_with_header(header_name):
    """
    :return: A responder answering 404 when the request carries header_name,
             which is how URLScan and SecureIIS reject unexpected headers
    """

    def respond(mock_response, request, uri, response_headers):
        response_headers["Content-Type"] = "text/html"
        if request.headers.get(header_name) is not None:
            return 404, response_headers, "Rejected"
        return 200, response_headers, "Hello world"

    return respond


class TestFingerprintWAFSignatures(PluginTest):
    """
    Run each WAF fingerprint method against a canned site which carries that
    WAF signature. The discover() method only runs once per scan, so the
    methods are called directly with the scan's URL opener.
    """

    target_url = "http://no-waf/"

    MOCK_RESPONSES: ClassVar[list] = [
        _waf_site("no-waf", {"Set-Cookie": "session=1", "Server": "nginx"}),
        _waf_site("airlock", {"Set-Cookie": "AL_SESS=1"}),
        _waf_site("barracuda", {"Set-Cookie": "barra_counter_session=1"}),
        _waf_site("cloudflare", {"Set-Cookie": "__cfduid=1"}),
        _waf_site("dotdefender", {"Set-Cookie": "X-dotDefender-denied=1"}),
        _waf_site("denyall", {"Set-Cookie": "sessioncookie=1"}),
        _waf_site("f5asm-cookie", {"Set-Cookie": "TS01abcd=1"}),
        _waf_site("f5asm-cnection", {"X-Cnection": "close"}),
        _waf_site("trafficshield", {"Set-Cookie": "ASINFO=1"}),
        _waf_site("fortiweb", {"Set-Cookie": "FORTIWAFSID=1"}),
        _waf_site("incapsula", {"Set-Cookie": "visid_incap_123=1"}),
        _waf_site("incapsula-ses", {"Set-Cookie": "incap_ses_12_123=1"}),
        _waf_site("websphere", {"Set-Cookie": "X-Backside-Transport=1"}),
        _waf_site("profense-cookie", {"Set-Cookie": "PLBSID=1"}),
        _waf_site("profense-server", {"Server": "Profense"}),
        _waf_site("teros", {"Set-Cookie": "st8id=1"}),
        _waf_site("netcontinuum", {"Set-Cookie": "NCI__SessionId=1"}),
        _waf_site("binarysec", {"Server": "BinarySec/3.2"}),
        _waf_site("hyperguard", {"Set-Cookie": "WODSESSION=1"}),
        MockResponse("http://urlscan/", _not_found_with_header("If")),
        MockResponse("http://secureiis/", _not_found_with_header("Transfer-Encoding")),
        MockResponse("http://missing/", "Not found", status=404),
    ]

    SIGNATURES: ClassVar[list] = [
        ("_fingerprint_Airlock", "airlock", "Airlock"),
        ("_fingerprint_Barracuda", "barracuda", "Barracuda"),
        ("_fingerprint_CloudFlare", "cloudflare", "CloudFlare"),
        ("_fingerprint_dotDefender", "dotdefender", "dotDefender"),
        ("_fingerprint_DenyAll", "denyall", "Deny All rWeb"),
        ("_fingerprint_F5ASM", "f5asm-cookie", "F5 ASM"),
        ("_fingerprint_F5ASM", "f5asm-cnection", "F5 ASM"),
        ("_fingerprint_F5TrafficShield", "trafficshield", "F5 TrafficShield"),
        ("_fingerprint_FortiWeb", "fortiweb", "FortiWeb"),
        ("_fingerprint_Incapsula", "incapsula", "Incapsula"),
        ("_fingerprint_Incapsula", "incapsula-ses", "Incapsula"),
        ("_fingerprint_IBMWebSphere", "websphere", "IBM WebSphere"),
        ("_fingerprint_Profense", "profense-cookie", "Profense"),
        ("_fingerprint_Profense", "profense-server", "Profense"),
        ("_fingerprint_TEROS", "teros", "TEROS"),
        ("_fingerprint_NetContinuum", "netcontinuum", "NetContinuum"),
        ("_fingerprint_BinarySec", "binarysec", "BinarySec"),
        ("_fingerprint_HyperGuard", "hyperguard", "HyperGuard"),
        ("_fingerprint_URLScan", "urlscan", "URLScan"),
        ("_fingerprint_SecureIIS", "secureiis", "SecureIIS"),
    ]

    def setUp(self):
        super().setUp()
        self.plugin = fingerprint_waf()
        self.plugin.set_url_opener(self.w3afcore.uri_opener)
        self.plugin.set_knowledge_base(self.kb)

    def _fingerprint(self, method_name, host):
        method = getattr(self.plugin, method_name)
        method(FuzzableRequest(URL(f"http://{host}/")))

    def test_each_signature_is_reported(self):
        for method_name, host, waf_name in self.SIGNATURES:
            with self.subTest(waf=waf_name, host=host):
                self.kb.cleanup()

                self._fingerprint(method_name, host)

                infos = self.kb.get("fingerprint_waf", waf_name)
                self.assertEqual(len(infos), 1, infos)
                self.assertEqual(infos[0].get_url(), URL(f"http://{host}/"))

    def test_site_without_waf_is_not_reported(self):
        for method_name, _, _ in self.SIGNATURES:
            self._fingerprint(method_name, "no-waf")

        self._fingerprint("_fingerprint_URLScan", "missing")
        self.plugin._fingerprint_ModSecurity(FuzzableRequest(URL("http://no-waf/")))

        self.assertEqual(self.kb.get_all_findings(), [])


class TestFingerprintWAFDescription(unittest.TestCase):
    def test_depends_on_active_filter_detection(self):
        plugin = fingerprint_waf()

        self.assertEqual(plugin.get_plugin_deps(), ["infrastructure.afd"])
        self.assertIn("infrastructure.afd", plugin.get_long_desc())
