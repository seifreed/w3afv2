"""
test_afd.py

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
import socket
import unittest
import urllib.parse
from typing import ClassVar

import w3af.core.controllers.output_manager as om
from w3af.core.data.kb.knowledge_base import DBKnowledgeBase
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.request.fuzzable_request import FuzzableRequest
from w3af.core.data.url.extended_urllib import ExtendedUrllib
from w3af.plugins.infrastructure.afd import afd
from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest

BAD_SIG_URI = re.compile(".*(passwd|uname|passthru|xp_cmdshell|WINNT).*", re.IGNORECASE)


class TestFoundAFD(PluginTest):

    target_url = "http://httpretty/"

    _run_configs: ClassVar[dict] = {
        "cfg": {
            "target": target_url,
            "plugins": {"infrastructure": (PluginConfig("afd"),)},
        }
    }

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(target_url, "Home page"),
        MockResponse(BAD_SIG_URI, "Blocked by WAF"),
        MockResponse(re.compile(target_url + ".*"), "Another page"),
    ]

    def test_afd_found_http(self):
        cfg = self._run_configs["cfg"]
        self._scan(self.target_url, cfg["plugins"])

        infos = self.kb.get("afd", "afd")

        self.assertEqual(len(infos), 1, infos)
        info = infos[0]

        self.assertEqual(info.get_name(), "Active filter detected")
        values = [
            urllib.parse.unquote_plus(u.url_string.split("=")[1])
            for u in info["filtered"]
        ]

        self.assertIn("../../../../etc/passwd", set(values), values)


MOD_SECURITY_ANSWER = """\
<!DOCTYPE HTML PUBLIC "-//IETF//DTD HTML 2.0//EN">
<html><head>
<title>403 Forbidden</title>
</head><body>
<h1>Forbidden</h1>
<p>You don't have permission to access /
on this server.<br />
</p>
</body></html>
"""


class TestAFDShortResponses(PluginTest):

    target_url = "http://httpretty/"

    _run_configs: ClassVar[dict] = {
        "cfg": {
            "target": target_url,
            "plugins": {"infrastructure": (PluginConfig("afd"),)},
        }
    }

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(target_url, "hello world"),
        MockResponse(BAD_SIG_URI, MOD_SECURITY_ANSWER, status=403),
        MockResponse(re.compile(target_url + r"\?.*"), "hello world"),
    ]

    def test_afd_found(self):
        cfg = self._run_configs["cfg"]
        self._scan(self.target_url, cfg["plugins"])

        infos = self.kb.get("afd", "afd")

        self.assertEqual(len(infos), 1, infos)
        info = infos[0]

        self.assertEqual(info.get_name(), "Active filter detected")
        values = [
            urllib.parse.unquote_plus(u.url_string.split("=")[1])
            for u in info["filtered"]
        ]

        self.assertIn("../../../../etc/passwd", set(values), values)


class TestFoundHttpsAFD(TestFoundAFD):

    target_url = "https://httpretty/"

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(target_url, "Home page"),
        MockResponse(BAD_SIG_URI, "Blocked by WAF"),
        MockResponse(re.compile(target_url + ".*"), "Another page"),
    ]


class TestNotFoundAFD(PluginTest):

    target_url = "http://httpretty/"

    _run_configs: ClassVar[dict] = {
        "cfg": {
            "target": target_url,
            "plugins": {"infrastructure": (PluginConfig("afd"),)},
        }
    }

    MOCK_RESPONSES: ClassVar[list] = [MockResponse(re.compile(".*"), "Static page")]

    def test_afd_not_found_http(self):
        cfg = self._run_configs["cfg"]
        self._scan(self.target_url, cfg["plugins"])

        infos = self.kb.get("afd", "afd")
        self.assertEqual(len(infos), 0, infos)


def closed_port_url():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    return URL(f"http://127.0.0.1:{port}/")


class TestAFDUnreachable(unittest.TestCase):
    """
    Without the plugin URL opener proxy, which turns failed requests into 204
    responses, the plugin itself has to handle the request errors.
    """

    def setUp(self):
        kb.cleanup()
        self.plugin = afd()
        self.plugin.set_output(om.out)
        self.plugin._uri_opener = ExtendedUrllib()
        self.addCleanup(self.plugin._uri_opener.end)

    def test_first_request_fails(self):
        self.plugin.discover(FuzzableRequest(closed_port_url()), 1)

        self.assertEqual(kb.get("afd", "afd"), [])

    def test_offending_request_fails_is_filtered(self):
        offending_url = closed_port_url()

        self.plugin._send_and_analyze("payload", offending_url, "body", "param")

        self.assertEqual(self.plugin._filtered, [offending_url])

    def test_long_description(self):
        self.assertIn("active filter", self.plugin.get_long_desc())


kb = DBKnowledgeBase()
