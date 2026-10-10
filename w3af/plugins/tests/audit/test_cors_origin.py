"""
test_cors_origin.py

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
import urllib.parse
from typing import ClassVar

from w3af.core.data.dc.headers import Headers
from w3af.core.data.kb.info_set import InfoSet
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.request.fuzzable_request import FuzzableRequest
from w3af.core.data.url.http_response import HTTPResponse
from w3af.plugins.audit.cors_origin import cors_origin
from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest

CORS_URL = "http://mock/w3af/audit/cors/"

CORS_INDEX = """
<a href="echo-origin.py">Echo origin</a>
<a href="echo-origin-2.py">Echo origin again</a>
<a href="no-cors.py">No CORS</a>
"""


def echo_origin(mock_response, request, uri, response_headers):
    """Reflect the request Origin header into Access-Control-Allow-Origin."""
    response_headers["Content-Type"] = "text/html"
    origin = request.headers.get("Origin")
    if origin is not None:
        response_headers["Access-Control-Allow-Origin"] = origin
    return 200, response_headers, "<html>CORS enabled</html>"


def no_cors(mock_response, request, uri, response_headers):
    response_headers["Content-Type"] = "text/html"
    return 200, response_headers, "<html>No CORS here</html>"


CORS_PAGES = {
    "echo-origin.py": echo_origin,
    "echo-origin-2.py": echo_origin,
    "no-cors.py": no_cors,
}


def cors_site(mock_response, request, uri, response_headers):
    page = urllib.parse.urlsplit(request.uri).path.rsplit("/", 1)[-1]
    responder = CORS_PAGES.get(page)
    if responder is None:
        response_headers["Content-Type"] = "text/html"
        return 200, response_headers, CORS_INDEX
    return responder(mock_response, request, uri, response_headers)


class TestCORSOriginScan(PluginTest):

    target_url = CORS_URL
    originator = "http://mock/"

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(re.compile(f"{re.escape(CORS_URL)}.*"), cors_site)
    ]

    _run_configs: ClassVar[dict] = {
        "cfg": {
            "target": target_url,
            "plugins": {
                "audit": (
                    PluginConfig(
                        "cors_origin",
                        ("origin_header_value", originator, PluginConfig.STR),
                        ("expected_http_response_code", 200, PluginConfig.INT),
                    ),
                ),
                "crawl": (
                    PluginConfig(
                        "web_spider", ("only_forward", True, PluginConfig.BOOL)
                    ),
                ),
            },
        }
    }

    def test_scan(self):
        cfg = self._run_configs["cfg"]
        self._scan(cfg["target"], cfg["plugins"])

        vulns = self.kb.get("cors_origin", "cors_origin")

        self.assertAllVulnNamesEqual("Insecure Access-Control-Allow-Origin", vulns)

        reported_urls = {
            info.get_url().url_string for info_set in vulns for info in info_set.infos
        }
        self.assertEqual(
            reported_urls,
            {f"{CORS_URL}echo-origin.py", f"{CORS_URL}echo-origin-2.py"},
        )

        self.assertTrue(
            all(v.get_url().url_string.startswith(self.target_url) for v in vulns)
        )


class TestCORSOrigin(PluginTest):
    def setUp(self):
        super().setUp()

        self.co = cors_origin()
        self.co.set_knowledge_base(self.kb)

        self.url = URL("http://moth/")
        self.origin = "http://moth/"
        self.response = HTTPResponse(200, "", Headers(), self.url, self.url, _id=3)
        self.request = FuzzableRequest(self.url)

    def test_allow_methods_no(self):
        allow_methods = "GET, POST, Options"
        allow_origin = "http://w3af.org/"
        allow_credentials = "false"

        self.co._allow_methods(
            self.request,
            self.url,
            self.origin,
            self.response,
            allow_origin,
            allow_credentials,
            allow_methods,
        )
        vulns = self.kb.get("cors_origin", "cors_origin")

        self.assertEqual(vulns, [])

    def test_allow_methods_strange(self):

        allow_methods = "GET, POST, OPTIONS, FOO"
        allow_origin = "http://w3af.org/"
        allow_credentials = "false"

        self.co._allow_methods(
            self.request,
            self.url,
            self.origin,
            self.response,
            allow_origin,
            allow_credentials,
            allow_methods,
        )
        vulns = self.kb.get("cors_origin", "cors_origin")

        self.assertEqual(len(vulns), 1)
        vuln = vulns[0]

        self.assertEqual(vuln.get_name(), "Uncommon CORS methods enabled")
        self.assertNotEqual(vuln.get_desc(), None)

    def test_allow_methods_sensitive(self):

        allow_methods = "GET, POST, OPTIONS, PUT"
        allow_origin = "http://w3af.org/"
        allow_credentials = "false"

        self.co._allow_methods(
            self.request,
            self.url,
            self.origin,
            self.response,
            allow_origin,
            allow_credentials,
            allow_methods,
        )
        vulns = self.kb.get("cors_origin", "cors_origin")

        self.assertEqual(len(vulns), 1)
        vuln = vulns[0]

        self.assertEqual(vuln.get_name(), "Sensitive CORS methods enabled")
        self.assertNotEqual(vuln.get_desc(), None)

    def test_allow_methods_sensitive_strange(self):

        allow_methods = "GET, POST, OPTIONS, PUT, FOO"
        allow_origin = "http://w3af.org/"
        allow_credentials = "false"

        self.co._allow_methods(
            self.request,
            self.url,
            self.origin,
            self.response,
            allow_origin,
            allow_credentials,
            allow_methods,
        )
        vulns = self.kb.get("cors_origin", "cors_origin")

        self.assertEqual(len(vulns), 2)
        vuln_names = {v.get_name() for v in vulns}
        expected_vuln_names = {
            "Sensitive CORS methods enabled",
            "Uncommon CORS methods enabled",
        }

        self.assertEqual(vuln_names, expected_vuln_names)
        self.assertIsNotNone(vulns[0].get_desc())
        self.assertIsNotNone(vulns[1].get_desc())

    def test_allow_methods_sensitive_call_max(self):

        allow_methods = "GET, POST, OPTIONS, PUT"
        allow_origin = "http://w3af.org/"
        allow_credentials = "false"

        for i in range(InfoSet.MAX_INFO_INSTANCES + 2):

            self.co._allow_methods(
                self.request,
                self.url,
                self.origin,
                self.response,
                allow_origin,
                allow_credentials,
                allow_methods,
            )
            vulns = self.kb.get("cors_origin", "cors_origin")

            self.assertEqual(len(vulns), 1)
            v = vulns[0]

            msg = f"Failure on run #{i}"
            self.assertEqual(v.get_name(), "Sensitive CORS methods enabled", msg)

    def test_universal_allow_not(self):
        allow_methods = "GET, POST, OPTIONS"
        allow_origin = "http://w3af.org/"
        allow_credentials = "false"

        self.co._analyze_server_response(
            self.request,
            self.url,
            self.origin,
            self.response,
            allow_origin,
            allow_credentials,
            allow_methods,
        )
        vulns = self.kb.get("cors_origin", "cors_origin")

        self.assertEqual(len(vulns), 0, vulns)

    def test_universal_allow_yes(self):
        allow_methods = "GET, POST, OPTIONS"
        allow_origin = "*"
        allow_credentials = "false"

        self.co._analyze_server_response(
            self.request,
            self.url,
            self.origin,
            self.response,
            allow_origin,
            allow_credentials,
            allow_methods,
        )
        vulns = self.kb.get("cors_origin", "cors_origin")

        self.assertEqual(len(vulns), 1, vulns)
        vuln = vulns[0]

        self.assertEqual(vuln.get_name(), 'Access-Control-Allow-Origin set to "*"')
        self.assertNotEqual(vuln.get_desc(), None)

    def test_universal_origin_echo_false(self):
        allow_methods = "GET, POST, OPTIONS"
        allow_origin = "http://www.google.com/"
        allow_credentials = "false"
        self.co._analyze_server_response(
            self.request,
            self.url,
            self.origin,
            self.response,
            allow_origin,
            allow_credentials,
            allow_methods,
        )
        vulns = self.kb.get("cors_origin", "cors_origin")

        self.assertEqual(len(vulns), 0, vulns)

    def test_universal_origin_echo_without_credentials(self):
        allow_methods = "GET, POST, OPTIONS"
        allow_origin = "http://moth/"
        allow_credentials = "false"
        self.co._analyze_server_response(
            self.request,
            self.url,
            self.origin,
            self.response,
            allow_origin,
            allow_credentials,
            allow_methods,
        )
        vulns = self.kb.get("cors_origin", "cors_origin")

        self.assertEqual(len(vulns), 1, vulns)
        vuln = vulns[0]

        self.assertEqual(vuln.get_name(), "Insecure Access-Control-Allow-Origin")
        self.assertNotEqual(vuln.get_desc(), None)

    def test_universal_origin_echo_with_credentials(self):
        allow_methods = "GET, POST, OPTIONS"
        allow_origin = "http://moth/"
        allow_credentials = "true"
        self.co._analyze_server_response(
            self.request,
            self.url,
            self.origin,
            self.response,
            allow_origin,
            allow_credentials,
            allow_methods,
        )
        vulns = self.kb.get("cors_origin", "cors_origin")

        self.assertEqual(len(vulns), 1, vulns)
        vuln = vulns[0]

        self.assertEqual(
            vuln.get_name(), "Insecure Access-Control-Allow-Origin with credentials"
        )
        self.assertNotEqual(vuln.get_desc(), None)

    def test_universal_origin_allow_creds(self):
        allow_methods = "GET, POST, OPTIONS"
        allow_origin = "*"
        allow_credentials = "true"
        self.co._analyze_server_response(
            self.request,
            self.url,
            self.origin,
            self.response,
            allow_origin,
            allow_credentials,
            allow_methods,
        )
        vulns = self.kb.get("cors_origin", "cors_origin")
        self.assertEqual(len(vulns), 2, vulns)

        name_creds = "Incorrect withCredentials implementation"
        acao_star = 'Access-Control-Allow-Origin set to "*"'

        impl_err_vuln = [v for v in vulns if v.get_name() == name_creds]
        acao_all_vuln = [v for v in vulns if v.get_name() == acao_star]

        vuln = impl_err_vuln[0]
        self.assertEqual(vuln.get_name(), "Incorrect withCredentials implementation")
        self.assertNotEqual(vuln.get_desc(), None)

        vuln = acao_all_vuln[0]
        self.assertEqual(vuln.get_name(), 'Access-Control-Allow-Origin set to "*"')
        self.assertNotEqual(vuln.get_desc(), None)
