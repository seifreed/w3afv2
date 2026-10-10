"""
test_detect_transparent_proxy.py

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

import socket
import unittest

import w3af.core.data.kb.knowledge_base as kb
from w3af.core.controllers.exceptions import RunOnce
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.request.fuzzable_request import FuzzableRequest
from w3af.plugins.infrastructure.detect_transparent_proxy import (
    detect_transparent_proxy,
)

FUZZABLE_REQUEST = FuzzableRequest(URL("http://target/"))


def listening_socket(test_case):
    sock = socket.socket()
    test_case.addCleanup(sock.close)
    sock.bind(("127.0.0.1", 0))
    sock.listen()
    return sock.getsockname()


def closed_address():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()


class TestDetectTransparentProxy(unittest.TestCase):
    def setUp(self):
        kb.kb.cleanup()
        self.addCleanup(kb.kb.cleanup)

    def test_every_probe_answered_is_a_transparent_proxy(self):
        address = listening_socket(self)
        plugin = detect_transparent_proxy(probe_addresses=(address, address))
        plugin.set_knowledge_base(kb.kb)

        plugin.discover(FUZZABLE_REQUEST, 1)

        infos = kb.kb.get("detect_transparent_proxy", "detect_transparent_proxy")
        self.assertEqual(len(infos), 1, infos)
        self.assertEqual(infos[0].get_name(), "Transparent proxy detected")
        self.assertEqual(infos[0].get_url(), FUZZABLE_REQUEST.get_url())

    def test_unanswered_probe_means_no_proxy(self):
        address = listening_socket(self)
        plugin = detect_transparent_proxy(probe_addresses=(address, closed_address()))
        plugin.set_knowledge_base(kb.kb)

        plugin.discover(FUZZABLE_REQUEST, 1)

        self.assertEqual(
            kb.kb.get("detect_transparent_proxy", "detect_transparent_proxy"), []
        )

    def test_runs_once(self):
        plugin = detect_transparent_proxy(probe_addresses=(closed_address(),))
        plugin.set_knowledge_base(kb.kb)

        plugin.discover(FUZZABLE_REQUEST, 1)

        self.assertRaises(RunOnce, plugin.discover, FUZZABLE_REQUEST, 2)

    def test_probes_unroutable_port_80_by_default(self):
        plugin = detect_transparent_proxy()

        self.assertEqual(plugin._probe_addresses[0], ("1.2.3.4", 80))
        self.assertIn("transparent proxies", plugin.get_long_desc())
