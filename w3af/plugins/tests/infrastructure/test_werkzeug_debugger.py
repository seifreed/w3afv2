"""
test_jetleak.py

Copyright 2015 Andres Riancho

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
import threading
import unittest
from typing import ClassVar

from werkzeug.debug import DebuggedApplication
from werkzeug.serving import make_server
from werkzeug.wrappers import Response

from w3af.plugins.infrastructure.werkzeug_debugger import werkzeug_debugger
from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest

JS_RESOURCE = """
$(function() {
  var sourceView = null;

  /**
   * if we are in console mode, show the console.
   */
  if (CONSOLE_MODE && EVALEX) {
    openShell(null, $('div.console div.inner').empty(), 0);
  }

  $('div.traceback div.frame').each(function() {
    var
      target = $('pre', this)
        .click(function() {
          sourceButton.click();
        }),
      consoleNode = null, source = null,
      frameID = this.id.substring(6);

    /**
     * Add an interactive console to the frames
     */
    if (EVALEX)
      $('<img src="?__debugger__=yes&cmd=resource&f=console.png">')
"""


class TestWerkzeugDebuggerEnabled(PluginTest):
    target_url = "http://httpretty/"

    _run_configs: ClassVar[dict] = {
        "cfg": {
            "target": target_url,
            "plugins": {"infrastructure": (PluginConfig("werkzeug_debugger"),)},
        }
    }

    class CustomMockResponse(MockResponse):
        def get_response(self, http_request, uri, response_headers):
            if "__debugger__" in uri:
                body = JS_RESOURCE
                status = 200
            else:
                body = "Regular response"
                status = 200

            return status, response_headers, body

    MOCK_RESPONSES: ClassVar[list] = [
        CustomMockResponse(re.compile(".*"), body=None, method="GET", status=200)
    ]

    def test_vulnerable_werkzeug(self):
        cfg = self._run_configs["cfg"]

        self._scan(self.target_url, cfg["plugins"])

        vulns = self.kb.get("werkzeug_debugger", "werkzeug_debugger")

        self.assertEqual(len(vulns), 1, vulns)
        vuln = vulns[0]

        self.assertEqual(vuln.get_name(), "Werkzeug debugger enabled")


class TestWerkzeugDebuggerDisabled(PluginTest):

    target_url = "http://httpretty/"

    _run_configs: ClassVar[dict] = {
        "cfg": {
            "target": target_url,
            "plugins": {"infrastructure": (PluginConfig("werkzeug_debugger"),)},
        }
    }

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(
            re.compile(".*"), body="Regular response", method="GET", status=200
        )
    ]

    def test_vulnerable_werkzeug(self):
        cfg = self._run_configs["cfg"]

        self._scan(self.target_url, cfg["plugins"])

        vulns = self.kb.get("werkzeug_debugger", "werkzeug_debugger")
        self.assertEqual(len(vulns), 0, vulns)


class TestWerkzeugDebuggerRealDebugger(PluginTest):
    """
    Scan a real Werkzeug application with the interactive debugger enabled,
    served on an ephemeral 127.0.0.1 port.
    """

    def setUp(self):
        super().setUp()

        application = DebuggedApplication(Response("Hello World!"), evalex=True)
        self.debugger_server = make_server("127.0.0.1", 0, application, threaded=True)
        server_thread = threading.Thread(
            target=self.debugger_server.serve_forever, daemon=True
        )
        server_thread.start()

        self.addCleanup(self.debugger_server.server_close)
        self.addCleanup(server_thread.join)
        self.addCleanup(self.debugger_server.shutdown)

    def test_vulnerable_werkzeug(self):
        target_url = f"http://127.0.0.1:{self.debugger_server.server_port}/"
        plugins = {"infrastructure": (PluginConfig("werkzeug_debugger"),)}

        self._scan(target_url, plugins)

        vulns = self.kb.get("werkzeug_debugger", "werkzeug_debugger")
        self.assertEqual(len(vulns), 1, vulns)


class TestWerkzeugDebuggerDescription(unittest.TestCase):
    def test_long_desc_mentions_code_execution(self):
        self.assertIn(
            "execute\n        arbitrary Python code",
            werkzeug_debugger().get_long_desc(),
        )
