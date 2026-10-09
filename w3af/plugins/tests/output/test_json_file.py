"""
test_json_file.py

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

import contextlib
import json
import os
import re
import urllib.parse
from typing import ClassVar

import pytest

from w3af.core.data.kb.tests.test_vuln import MockVuln
from w3af.core.data.parsers.doc.url import URL
from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest
from w3af.tests.helpers.sqli_site import SQL_ERROR


def _sqli_integer(mock_response, request, uri, response_headers):
    """
    Emulate an error-based SQL injection in an integer query-string parameter:
    the value is concatenated into the query without escaping, so an unbalanced
    quote produces a MySQL syntax error.
    """
    response_headers["content-type"] = "text/html"
    query = urllib.parse.urlsplit(request.uri).query
    value = urllib.parse.parse_qs(query).get("id", [""])[0]

    if value.count("'") % 2 == 1 or '"' in value:
        body = f"<html><body>{SQL_ERROR} near '{value}' at line 1</body></html>"
    else:
        body = f"<html><body>Results for {value}</body></html>"

    return 200, response_headers, body


@pytest.mark.smoke
class TestJsonOutput(PluginTest):

    target_url = "http://mock/audit/sql_injection/where_integer_qs.py"

    FILENAME = "output-unittest.json"

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(
            re.compile(r"http://mock/audit/sql_injection/where_integer_qs\.py.*"),
            body=_sqli_integer,
            method="GET",
        ),
    ]

    _run_configs: ClassVar[dict] = {
        "cfg": {
            "target": target_url + "?id=3",
            "plugins": {
                "audit": (PluginConfig("sqli"),),
                "output": (
                    PluginConfig(
                        "json_file", ("output_file", FILENAME, PluginConfig.STR)
                    ),
                ),
            },
        }
    }

    def test_found_vuln(self):
        cfg = self._run_configs["cfg"]
        self._scan(cfg["target"], cfg["plugins"])

        kb_vulns = self.kb.get("sqli", "sqli")
        file_vulns = self._from_json_get_vulns(self.FILENAME)

        self.assertEqual(len(kb_vulns), 1, kb_vulns)

        self.assertEqual(
            {v.get_url() for v in kb_vulns},
            {v.get_url() for v in file_vulns},
            {v.get_url() for v in kb_vulns},
        )

        self.assertEqual(
            {v.get_name() for v in kb_vulns},
            {v.get_name() for v in file_vulns},
            {v.get_name() for v in kb_vulns},
        )

        self.assertEqual(
            {v.get_plugin_name() for v in kb_vulns},
            {v.get_plugin_name() for v in file_vulns},
            {v.get_plugin_name() for v in kb_vulns},
        )

    def _from_json_get_vulns(self, filename):
        with open(filename) as json_fd:
            json_data = json.load(json_fd)
        vulns = []

        for finding in json_data["items"]:

            v = MockVuln(finding["Name"], None, "High", 1, "sqli")
            v.set_url(URL(finding["URL"]))
            vulns.append(v)

        return vulns

    def tearDown(self):
        super().tearDown()
        with contextlib.suppress(OSError):
            os.remove(self.FILENAME)
        self.kb.cleanup()
