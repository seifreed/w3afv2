"""
canned_plugin_test.py

Copyright 2026 w3af contributors

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
from typing import ClassVar

import w3af.core.controllers.output_manager as om
from w3af.core.controllers.core_helpers.fingerprint_404 import Fingerprint404
from w3af.core.controllers.plugins.plugin import Plugin
from w3af.core.data.kb.config import Config
from w3af.core.data.kb.knowledge_base import DBKnowledgeBase
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.url.extended_urllib import ExtendedUrllib
from w3af.plugins.tests.canned_http_server import (
    CannedHTTPServer,
    CannedReply,
    CannedRequest,
)


def closed_port_url():
    """
    :return: A URL pointing to a local port where nothing is listening
    """
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    return URL(f"http://127.0.0.1:{port}/")


class CannedServerPluginTest(unittest.TestCase):
    """
    Runs a plugin outside a scan, sending its HTTP requests through a canned
    HTTP server (acting as proxy) which answers them using ``respond``.
    """

    plugin_class: ClassVar[type[Plugin]]

    def setUp(self):
        kb.cleanup()
        self.addCleanup(kb.cleanup)

        self.server = CannedHTTPServer(self.respond)
        self.server.start()
        self.addCleanup(self.server.stop)

        self.uri_opener = ExtendedUrllib(configuration=cf)
        self.uri_opener.settings.set_proxy(self.server.host, self.server.port)
        self.addCleanup(self.uri_opener.end)

        self.plugin = self.plugin_class()
        self.plugin.set_url_opener(self.uri_opener)
        self.plugin.set_knowledge_base(kb)
        self.plugin.set_output(om.out)
        self.plugin.set_configuration(cf)
        self.fingerprint_404 = Fingerprint404(om.out, cf)
        self.plugin.set_fingerprint_404(self.fingerprint_404)
        self.addCleanup(self.fingerprint_404.cleanup)

    def respond(self, request: CannedRequest) -> CannedReply:
        raise NotImplementedError


cf = Config()


kb = DBKnowledgeBase()
