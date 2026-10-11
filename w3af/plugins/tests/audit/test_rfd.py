"""
test_rfd.py

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
from typing import ClassVar

from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest

RUN_CONFIG = {
    "cfg": {
        "target": None,
        "plugins": {
            "audit": (PluginConfig("rfd"),),
            "crawl": (
                PluginConfig("web_spider", ("only_forward", True, PluginConfig.BOOL)),
            ),
        },
    }
}


def safe_json_responder(mock_response, request, uri, response_headers):
    response_headers["Content-Type"] = "text/json"
    response_headers["Content-Disposition"] = 'attachment; filename="safe.json"'
    return 200, response_headers, '{"q": "rfd"}'


class TestJSONAllFiltered(PluginTest):

    target_url = "http://json-all-filtered/?q=rfd"

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(
            url="http://json-all-filtered/?q=rfd",
            body='{"q": "rfd"}',
            content_type="text/json",
            method="GET",
            status=200,
        ),
        MockResponse(
            url="http://json-all-filtered/%3B/w3af.cmd%3B/" "w3af.cmd?q=rfd",
            body='message "w3afExecToken"',
            content_type="text/json",
            method="GET",
            status=200,
        ),
        MockResponse(
            url="http://json-all-filtered/%3B/w3af.cmd%3B/" "w3af.cmd?q=w3afExecToken",
            body='    {"a":"w3afExecToken","b":"b"}',
            content_type="text/json",
            method="GET",
            status=200,
        ),
        MockResponse(
            url="http://json-all-filtered/%3B/w3af.cmd%3B/"
            "w3af.cmd?q=w3afExecToken%22%26%7C%0A",
            body='    {"a":"w3afExecToken","b":"b"}',
            content_type="application/javascript",
            method="GET",
            status=200,
        ),
    ]

    def test_not_found_json_all_filtered(self):
        cfg = RUN_CONFIG["cfg"]
        self._scan(self.target_url, cfg["plugins"])
        vulns = self.kb.get("rfd", "rfd")
        self.assertEqual(0, len(vulns))


class TestJSON(PluginTest):

    target_url = "http://json/?q=rfd"

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(
            url="http://json/?q=rfd",
            body='{"q": "rfd"}',
            content_type="text/json",
            method="GET",
            status=200,
        ),
        MockResponse(
            url="http://json/%3B/w3af.cmd%3B/w3af.cmd?q=rfd",
            body='message "w3afExecToken"',
            content_type="text/json",
            method="GET",
            status=200,
        ),
        MockResponse(
            url="http://json/%3B/w3af.cmd%3B/w3af.cmd?" "q=w3afExecToken",
            body='    {"a":"w3afExecToken","b":"b"}',
            content_type="text/json",
            method="GET",
            status=200,
        ),
        MockResponse(
            url="http://json/%3B/w3af.cmd%3B/w3af.cmd?" "q=w3afExecToken%22%26%7C%0A",
            body='    {"a":"w3afExecToken"&|\n","b":"b"}',
            content_type="application/javascript",
            method="GET",
            status=200,
        ),
    ]

    def test_found_json(self):
        cfg = RUN_CONFIG["cfg"]
        self._scan(self.target_url, cfg["plugins"])
        vulns = self.kb.get("rfd", "rfd")
        self.assertEqual(1, len(vulns))


class TestJSONDobleQuotesFiltered(PluginTest):

    target_url = "http://json-filtered/?q=rfd"

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(
            url="http://json-filtered/?q=rfd",
            body='{"q": "rfd"}',
            content_type="text/json",
            method="GET",
            status=200,
        ),
        MockResponse(
            url="http://json-filtered/%3B/w3af.cmd%3B/w3af.cmd?q=rfd",
            body='message "w3afExecToken"',
            content_type="text/json",
            method="GET",
            status=200,
        ),
        MockResponse(
            url="http://json-filtered/%3B/w3af.cmd%3B/w3af.cmd?" "q=w3afExecToken",
            body='    {"a":"w3afExecToken","b":"b"}',
            content_type="text/json",
            method="GET",
            status=200,
        ),
        MockResponse(
            url="http://json-filtered/%3B/w3af.cmd%3B/w3af.cmd?"
            "q=w3afExecToken%22%26%7C%0A",
            body='    {"a":"w3afExecToken&|\n","b":"b"}',
            content_type="application/javascript",
            method="GET",
            status=200,
        ),
    ]

    def test_not_found_json(self):
        cfg = RUN_CONFIG["cfg"]
        self._scan(self.target_url, cfg["plugins"])
        vulns = self.kb.get("rfd", "rfd")
        self.assertEqual(0, len(vulns))


class TestJSONP(PluginTest):

    target_url = "http://jsonp/?callback=rfd"

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(
            url="http://jsonp/?callback=rfd",
            body='{"q": "rfd"}',
            content_type="application/javascript",
            method="GET",
            status=200,
        ),
        MockResponse(
            url="http://jsonp/%3B/w3af.cmd%3B/w3af.cmd?callback" "=rfd",
            body='    rfd({ "Result": ' '{ "Timestamp": 1417601045 } }) ',
            content_type="application/javascript",
            method="GET",
            status=200,
        ),
        MockResponse(
            url="http://jsonp/%3B/w3af.cmd%3B/w3af.cmd?callback" "=w3afExecToken",
            body='    w3afExecToken({ "Result": ' '{ "Timestamp": 1417601045 } }) ',
            content_type="application/javascript",
            method="GET",
            status=200,
        ),
    ]

    def test_found_jsonp(self):
        cfg = RUN_CONFIG["cfg"]
        self._scan(self.target_url, cfg["plugins"])
        vulns = self.kb.get("rfd", "rfd")
        self.assertEqual(1, len(vulns))


class TestRFDContentDispositionFilename(PluginTest):

    target_url = "http://download/?q=rfd"

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(re.compile("http://download/.*"), safe_json_responder)
    ]

    def test_filename_disables_rfd(self):
        self._scan(self.target_url, RUN_CONFIG["cfg"]["plugins"])
        self.assertEqual([], self.kb.get("rfd", "rfd"))


class TestRFDNotVulnerableContentType(PluginTest):

    target_url = "http://html/?q=rfd"

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(
            re.compile("http://html/.*"),
            body="<html>rfd</html>",
            content_type="text/html",
        ),
    ]

    def test_html_disables_rfd(self):
        self._scan(self.target_url, RUN_CONFIG["cfg"]["plugins"])
        self.assertEqual([], self.kb.get("rfd", "rfd"))
