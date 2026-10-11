"""
test_vulners_db.py

Copyright 2018 Andres Riancho

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

The detection rules feed and the Vulners audit API are served by a local
HTTP server (LocalVulners) which answers from a small vulnerability database.
"""

import json
from typing import ClassVar

from w3af.core.data.constants import severity
from w3af.core.data.kb.knowledge_base import DBKnowledgeBase
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.url.extended_urllib import ExtendedUrllib
from w3af.plugins.grep.vulners_db import vulners_db
from w3af.plugins.tests.canned_http_server import CannedHTTPServer, CannedReply
from w3af.plugins.tests.grep.grep_test_utils import (
    GrepPluginTestCase,
    make_request,
    make_response,
)
from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest

RULES = {
    "IIS": {
        "regex": r"Microsoft-IIS/([\d.]+)",
        "alias": "Microsoft IIS",
        "type": "software",
    },
    "nginx": {
        "regex": r"nginx/([\d.]+)",
        "alias": "cpe:/a:nginx:nginx",
        "type": "cpe",
    },
    "weird": {"regex": r"Weird/([\d.]+)", "alias": "weird", "type": "unknown"},
    "broken": {"regex": r"Broken/([\d.]+)", "alias": "broken", "type": "software"},
}

IIS_CVES = (
    "CVE-2010-2730",
    "CVE-2010-1256",
    "CVE-2010-3972",
    "CVE-2012-2531",
    "CVE-2010-1899",
)

DATABASE = {
    "Microsoft IIS 7.5": [
        {"id": cve, "title": f"{cve} in IIS", "cvss": {"score": 9.3}}
        for cve in IIS_CVES
    ],
    "cpe:/a:nginx:nginx:1.4.0": [
        {"id": "CVE-2013-2028", "description": "Stack overflow", "cvss": {"score": 5}},
        {"id": "CVE-2013-4547", "title": "URI parsing"},
        {"id": "NGINX-NO-TEXT"},
    ],
}

JSON = {"Content-Type": "application/json"}


class LocalVulners:
    """
    Serves the detection rules at /rules.json and a subset of the Vulners v4
    audit API at /api/v4/audit/software/.
    """

    def __init__(self):
        self.audit_requests = []
        self.server = CannedHTTPServer(self.respond)

    def url(self, path):
        return f"http://127.0.0.1:{self.server.port}{path}"

    def respond(self, request):
        if request.path == "/rules.json":
            return CannedReply(200, JSON, json.dumps(RULES))

        if request.path == "/api/v4/audit/software/":
            return self.audit(request)

        return CannedReply(404, JSON, "{}")

    def audit(self, request):
        if request.headers.get("X-Api-Key") != "local-key":
            return CannedReply(401, JSON, json.dumps({"error": "Invalid API key"}))

        body = request.parsed_body
        self.audit_requests.append(body)

        results = []
        for software in body["software"]:
            if isinstance(software, dict):
                if software["product"] == "broken":
                    return CannedReply(400, JSON, json.dumps({"error": "Bad product"}))
                software = f"{software['product']} {software['version']}"

            results.append(
                {"input": software, "vulnerabilities": DATABASE.get(software, [])}
            )

        return CannedReply(200, JSON, json.dumps({"result": results}))


class TestVulnersDB(PluginTest):

    target_url = "http://httpretty"

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(
            "http://httpretty/",
            body="",
            method="GET",
            status=200,
            headers={
                "content-length": "0",
                "server": "Microsoft-IIS/7.5",
                "x-aspnet-version": "2.0.50727",
                "x-powered-by": "ASP.NET",
                "microsoftsharepointteamservices": "14.0.0.4762",
            },
        ),
        MockResponse(
            "http://httpretty/rules.json",
            body=json.dumps(RULES),
            content_type="application/json",
        ),
    ]

    def test_vulns_detected(self):
        api = LocalVulners()
        api.server.start()
        self.addCleanup(api.server.stop)

        plugins = {
            "grep": (
                PluginConfig(
                    "vulners_db",
                    ("vulners_api_key", "local-key", PluginConfig.STR),
                    ("vulners_api_url", api.url("/"), PluginConfig.URL),
                    (
                        "vulners_rules_url",
                        "http://httpretty/rules.json",
                        PluginConfig.URL,
                    ),
                ),
            ),
            "crawl": (
                PluginConfig("web_spider", ("only_forward", True, PluginConfig.BOOL)),
            ),
        }
        self._scan(self.target_url, plugins)

        vulns = self.kb.get("vulners_db", "HTML")

        self.assertEqual({i.get_name() for i in vulns}, set(IIS_CVES))

        vuln = next(i for i in vulns if i.get_name() == "CVE-2012-2531")

        self.assertEqual(vuln.get_url().url_string, "http://httpretty/")
        self.assertEqual(vuln.get_severity(), severity.HIGH)

        expected_desc = (
            "Vulners plugin detected software with known vulnerabilities."
            ' The identified vulnerability is "CVE-2012-2531".\n'
            "\n"
            " The first ten URLs where vulnerable software was detected are:\n"
            " - http://httpretty/\n"
        )
        self.assertEqual(vuln.get_desc(with_id=False), expected_desc)


class TestVulnersDBUnit(GrepPluginTestCase):

    def setUp(self):
        super().setUp()
        kb.cleanup()
        self.addCleanup(kb.cleanup)

        self.api = LocalVulners()
        self.api.server.start()
        self.addCleanup(self.api.server.stop)

        self.uri_opener = ExtendedUrllib()
        self.addCleanup(self.uri_opener.end)

    def make_plugin(self, api_key="local-key", rules_path="/rules.json"):
        plugin = vulners_db()
        options = plugin.get_options()
        options["vulners_api_key"].set_value(api_key)
        options["vulners_api_url"].set_value(self.api.url("/"))
        options["vulners_rules_url"].set_value(self.api.url(rules_path))
        plugin.set_options(options)
        self.configure_plugin(plugin)
        plugin.set_knowledge_base(kb)
        plugin.set_url_opener(self.uri_opener)
        return plugin

    def grep(self, plugin, server, path="/", content_type="text/html"):
        url = f"http://www.w3af.com{path}"
        response = make_response(
            url=url, content_type=content_type, headers=[("Server", server)]
        )
        plugin.grep(make_request(url=url), response)
        return kb.get("vulners_db", "HTML")

    def test_software_rule(self):
        plugin = self.make_plugin()

        vulns = self.grep(plugin, "Microsoft-IIS/7.5")

        self.assertEqual({v.get_name() for v in vulns}, set(IIS_CVES))
        self.assertEqual(
            self.api.audit_requests[0]["software"],
            [{"product": "Microsoft IIS", "version": "7.5"}],
        )
        self.assertEqual(
            self.api.audit_requests[0]["fields"], ["title", "description", "cvss"]
        )

    def test_cpe_rule_and_bulletin_descriptions(self):
        plugin = self.make_plugin()

        vulns = {v.get_name(): v for v in self.grep(plugin, "nginx/1.4.0")}

        self.assertEqual(
            self.api.audit_requests[0]["software"], ["cpe:/a:nginx:nginx:1.4.0"]
        )
        self.assertEqual(
            set(vulns), {"CVE-2013-2028", "CVE-2013-4547", "NGINX-NO-TEXT"}
        )
        self.assertEqual(vulns["CVE-2013-2028"].get_severity(), severity.MEDIUM)
        self.assertEqual(vulns["NGINX-NO-TEXT"].get_severity(), severity.INFORMATION)

        details = {
            name: vuln.first_info.get_desc(with_id=False)
            for name, vuln in vulns.items()
        }
        self.assertEqual(
            details["CVE-2013-2028"], "Vulners bulletin CVE-2013-2028: Stack overflow"
        )
        self.assertEqual(
            details["CVE-2013-4547"], "Vulners bulletin CVE-2013-4547: URI parsing"
        )
        self.assertEqual(
            details["NGINX-NO-TEXT"],
            "Vulners bulletin NGINX-NO-TEXT: no description available",
        )

    def test_results_are_cached(self):
        plugin = self.make_plugin()

        self.grep(plugin, "Microsoft-IIS/7.5", path="/a/")
        self.grep(plugin, "Microsoft-IIS/7.5", path="/b/")

        self.assertEqual(len(self.api.audit_requests), 1)

    def test_vulnerability_cache_is_bounded(self):
        plugin = self.make_plugin()

        for key in range(plugin.VULNERABILITY_CACHE_SIZE + 1):
            plugin._vulnerability_cache[key] = []

        self.assertEqual(
            len(plugin._vulnerability_cache), plugin.VULNERABILITY_CACHE_SIZE
        )

    def test_same_path_is_analyzed_once(self):
        plugin = self.make_plugin()

        self.grep(plugin, "nginx/1.4.0", path="/a/1.html")
        self.grep(plugin, "Microsoft-IIS/7.5", path="/a/2.html")

        self.assertEqual(len(self.api.audit_requests), 1)

    def test_non_text_responses_are_ignored(self):
        plugin = self.make_plugin()

        self.assertEqual(self.grep(plugin, "nginx/1.4.0", content_type="image/png"), [])
        self.assertEqual(self.api.audit_requests, [])

    def test_unknown_rule_type(self):
        plugin = self.make_plugin()

        self.assertEqual(self.grep(plugin, "Weird/1.0"), [])
        self.assertEqual(self.api.audit_requests, [])

    def test_api_error_is_not_cached(self):
        plugin = self.make_plugin()

        self.assertEqual(self.grep(plugin, "Broken/1.0", path="/a/"), [])
        self.assertEqual(self.grep(plugin, "Broken/1.0", path="/b/"), [])

        self.assertEqual(len(self.api.audit_requests), 2)

    def test_missing_api_key_disables_plugin(self):
        plugin = self.make_plugin(api_key="")

        self.assertEqual(self.grep(plugin, "Microsoft-IIS/7.5"), [])
        self.assertIsNone(plugin._vulners_api)
        self.assertIsNotNone(plugin.rules_table)

    def test_rules_download_failure(self):
        plugin = self.make_plugin(rules_path="/missing.json")

        self.assertEqual(self.grep(plugin, "Microsoft-IIS/7.5"), [])
        self.assertIsNone(plugin.rules_table)
        self.assertTrue(plugin.rules_updated)

    def test_check_vulners_requires_name_and_version(self):
        plugin = self.make_plugin()

        self.assertEqual(plugin.check_vulners("", "1.0", "software"), [])
        self.assertEqual(plugin.check_vulners("nginx", "", "software"), [])

    def test_options(self):
        plugin = self.make_plugin()
        options = plugin.get_options()

        self.assertEqual(options["vulners_api_key"].get_value(), "local-key")
        self.assertEqual(options["vulners_api_url"].get_value(), URL(self.api.url("/")))
        self.assertEqual(
            options["vulners_rules_url"].get_value(), URL(self.api.url("/rules.json"))
        )
        self.assertIn("API key", plugin.get_long_desc())


kb = DBKnowledgeBase()
