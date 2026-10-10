"""
test_detect_reverse_proxy.py

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

from typing import ClassVar

import w3af.core.data.kb.knowledge_base as kb
from w3af.core.data.kb.info import Info
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.request.fuzzable_request import FuzzableRequest
from w3af.core.exceptions import RunOnce
from w3af.plugins.infrastructure.detect_reverse_proxy import detect_reverse_proxy
from w3af.plugins.tests.canned_http_server import CannedReply
from w3af.plugins.tests.infrastructure.canned_plugin_test import (
    CannedServerPluginTest,
)

TARGET = FuzzableRequest(URL("http://target/"))


class ReverseProxyTest(CannedServerPluginTest):
    """
    The canned server answers each method with the reply in ``replies``, any
    other method gets an empty 200 response.
    """

    plugin_class = detect_reverse_proxy
    replies: ClassVar[dict[str, CannedReply]] = {}

    def respond(self, request):
        return self.replies.get(request.command, CannedReply(200, {}, ""))

    def discover(self):
        self.plugin.discover(TARGET, 1)
        return kb.kb.get("detect_reverse_proxy", "detect_reverse_proxy")

    def received_methods(self):
        return [request.command for request in self.server.requests]


class TestViaHeader(ReverseProxyTest):
    replies: ClassVar[dict[str, CannedReply]] = {
        "GET": CannedReply(200, {"Via": "1.1 squid"}, "")
    }

    def test_detected_with_get(self):
        infos = self.discover()

        self.assertEqual(len(infos), 1, infos)
        self.assertEqual(infos[0].get_name(), "Reverse proxy identified")
        self.assertEqual(self.received_methods(), ["GET"])

    def test_runs_once(self):
        self.discover()

        self.assertRaises(RunOnce, self.plugin.discover, TARGET, 2)

    def test_get_is_not_sent_behind_a_transparent_proxy(self):
        desc = "Your ISP seems to have a transparent proxy installed."
        transparent = Info("Transparent proxy detected", desc, 1, "plugin")
        kb.kb.append(
            "detect_transparent_proxy", "detect_transparent_proxy", transparent
        )

        self.assertEqual(self.discover(), [])
        self.assertEqual(self.received_methods(), ["TRACE", "TRACK"])


class TestTraceBody(ReverseProxyTest):
    replies: ClassVar[dict[str, CannedReply]] = {
        "TRACE": CannedReply(
            200,
            {"Content-Type": "message/http"},
            "TRACE / HTTP/1.1\nX-Forwarded-For:   10.0.0.1",
        )
    }

    def test_detected_with_trace(self):
        self.assertEqual(len(self.discover()), 1)
        self.assertEqual(self.received_methods(), ["GET", "TRACE"])


class TestTrackBody(ReverseProxyTest):
    replies: ClassVar[dict[str, CannedReply]] = {
        "TRACK": CannedReply(200, {}, "TRACK / HTTP/1.1\nReverse-Via : MUTUN")
    }

    def test_detected_with_track(self):
        self.assertEqual(len(self.discover()), 1)
        self.assertEqual(self.received_methods(), ["GET", "TRACE", "TRACK"])


class TestNoReverseProxy(ReverseProxyTest):
    def test_not_detected(self):
        self.assertEqual(self.discover(), [])
        self.assertEqual(self.received_methods(), ["GET", "TRACE", "TRACK"])

    def test_depends_on_transparent_proxy_detection(self):
        self.assertEqual(
            self.plugin.get_plugin_deps(), ["infrastructure.detect_transparent_proxy"]
        )
        self.assertIn("reverse proxy", self.plugin.get_long_desc())
