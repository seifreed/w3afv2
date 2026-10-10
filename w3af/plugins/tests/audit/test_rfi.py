"""
test_rfi.py

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

import http.client
import re
import socket
import threading
import unittest
from typing import ClassVar

import pytest

import w3af.core.controllers.output_manager as om
from w3af.core.controllers.daemons import webserver
from w3af.core.controllers.daemons.webserver import HTTPServer
from w3af.core.controllers.misc.get_unused_port import get_unused_port
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.request.fuzzable_request import FuzzableRequest
from w3af.core.exceptions import BaseFrameworkException
from w3af.plugins.audit.rfi import RFIWebHandler, rfi
from w3af.plugins.tests.audit.vulnerable_inclusion import (
    IncludePage,
    RemoteFetcher,
    execute_php,
)
from w3af.plugins.tests.audit.vulnerable_responses import html_page
from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest

LOCAL_ADDRESS = "127.0.0.1"
RFI_HOST = "10.1.2.3"
RFI_URL = f"http://{RFI_HOST}/audit/rfi/"
PUBLIC_RFI_URL = "http://8.8.8.8/audit/rfi/"
W3AF_SITE_PAGE = "http://w3af.org/rfi.html"
W3AF_SITE_CODE = '<?php echo "w3af"; echo " by Andres Riancho"; ?>'

FETCHER = RemoteFetcher(proxied_hosts=("w3af.org",))


def safe_page(mock_response, request, uri, response_headers):
    return html_page(response_headers, "Nothing is included here")


def rfi_responses():
    return [
        MockResponse(W3AF_SITE_PAGE, W3AF_SITE_CODE),
        MockResponse(
            re.compile(re.escape(RFI_URL + "rfi-rce.php") + r"(\?.*)?$"),
            IncludePage(FETCHER, execute=True),
        ),
        MockResponse(
            re.compile(re.escape(RFI_URL + "rfi-read.php") + r"(\?.*)?$"),
            IncludePage(FETCHER, execute=False),
        ),
        MockResponse(
            re.compile(re.escape(RFI_URL + "rfi-network-error.php") + r"(\?.*)?$"),
            IncludePage(FETCHER, network_error=True),
        ),
        MockResponse(
            re.compile(re.escape(RFI_URL + "rfi-safe.php") + r"(\?.*)?$"),
            safe_page,
        ),
        MockResponse(
            re.compile(re.escape(PUBLIC_RFI_URL + "rfi-rce.php") + r"(\?.*)?$"),
            IncludePage(FETCHER, execute=True),
        ),
    ]


def rfi_plugins(use_w3af_site, listen_port):
    return {
        "audit": (
            PluginConfig(
                "rfi",
                ("listen_address", LOCAL_ADDRESS, PluginConfig.STR),
                ("use_w3af_site", use_w3af_site, PluginConfig.BOOL),
                ("listen_port", listen_port, PluginConfig.INT),
            ),
        ),
    }


class TestRFI(PluginTest):

    target_url = RFI_URL
    target_rce = RFI_URL + "rfi-rce.php"
    target_read = RFI_URL + "rfi-read.php"
    target_network_error = RFI_URL + "rfi-network-error.php"
    target_safe = RFI_URL + "rfi-safe.php"

    MOCK_RESPONSES: ClassVar[list] = rfi_responses()

    def setUp(self):
        super().setUp()
        self.unused_port = get_unused_port()
        FETCHER.use_proxy(self.canned_server.host, self.canned_server.port)

    def scan_for_rfi(self, target, use_w3af_site):
        plugins = rfi_plugins(use_w3af_site, self.unused_port)
        self._scan(f"{target}?file=abc.txt", plugins)

        return self.kb.get("rfi", "rfi")

    def test_found_rfi_with_w3af_site(self):
        vulns = self.scan_for_rfi(self.target_rce, use_w3af_site=True)

        self.assertEqual(len(vulns), 1)

        vuln = vulns[0]
        self.assertEqual("Remote code execution", vuln.get_name())
        self.assertEqual(self.target_rce, vuln.get_url().url_string)

    @pytest.mark.smoke
    def test_found_rfi_with_local_server_rce(self):
        vulns = self.scan_for_rfi(self.target_rce, use_w3af_site=False)

        self.assertEqual(len(vulns), 1)

        vuln = vulns[0]
        self.assertEqual("Remote code execution", vuln.get_name())
        self.assertEqual(self.target_rce, vuln.get_url().url_string)

    def test_found_rfi_with_local_server_read(self):
        vulns = self.scan_for_rfi(self.target_read, use_w3af_site=False)

        self.assertEqual(len(vulns), 1)

        vuln = vulns[0]
        self.assertEqual("Remote file inclusion", vuln.get_name())
        self.assertEqual(self.target_read, vuln.get_url().url_string)

    def test_found_rfi_with_remote_server_read(self):
        vulns = self.scan_for_rfi(self.target_read, use_w3af_site=True)

        self.assertEqual(len(vulns), 1)

        vuln = vulns[0]
        self.assertEqual("Remote file inclusion", vuln.get_name())
        self.assertEqual(self.target_read, vuln.get_url().url_string)

    def test_potential_rfi_from_network_error(self):
        vulns = self.scan_for_rfi(self.target_network_error, use_w3af_site=False)

        self.assertEqual(len(vulns), 1)

        vuln = vulns[0]
        self.assertEqual("Potential remote file inclusion", vuln.get_name())
        self.assertEqual(self.target_network_error, vuln.get_url().url_string)

    def test_no_rfi_in_page_which_includes_nothing(self):
        vulns = self.scan_for_rfi(self.target_safe, use_w3af_site=True)

        self.assertEqual([], vulns)

    def test_private_listen_address_is_not_used_for_public_targets(self):
        plugins = rfi_plugins(use_w3af_site=False, listen_port=self.unused_port)

        self._scan(f"{PUBLIC_RFI_URL}rfi-rce.php?file=abc.txt", plugins)

        self.assertEqual([], self.kb.get("rfi", "rfi"))

    def test_local_server_is_not_used_when_listen_port_is_taken(self):
        busy_server = HTTPServer((LOCAL_ADDRESS, 0), ".", RFIWebHandler, om.out)
        self.addCleanup(busy_server.server_close)
        self.unused_port = busy_server.get_port()

        vulns = self.scan_for_rfi(self.target_rce, use_w3af_site=True)

        self.assertEqual(len(vulns), 1)
        self.assertEqual("Remote code execution", vulns[0].get_name())


class TestRFIWebServer(unittest.TestCase):

    def test_custom_web_server(self):
        RFIWebHandler.RESPONSE_BODY = '<? echo "hello world"; ?>'
        ws = HTTPServer((LOCAL_ADDRESS, 0), ".", RFIWebHandler, om.out)
        port = ws.get_port()

        server_thread = threading.Thread(target=ws.serve_forever)
        server_thread.name = "WebServer"
        server_thread.daemon = True
        server_thread.start()

        response_foobar = self.download(port, "/foobar")
        response_spameggs = self.download(port, "/spameggs")

        self.assertEqual(response_foobar, response_spameggs)
        self.assertEqual(response_foobar, RFIWebHandler.RESPONSE_BODY)

    @staticmethod
    def download(port, path):
        connection = http.client.HTTPConnection(LOCAL_ADDRESS, port, timeout=10)
        try:
            connection.request("GET", path)
            return connection.getresponse().read().decode("utf-8")
        finally:
            connection.close()


class TestExecutePhp(unittest.TestCase):

    def test_blocks_are_executed_and_the_rest_is_kept(self):
        source = 'a<?php echo "b"; echo "c"; ?>d<? echo "e"; ?>f<% out.print("g"); %>'

        self.assertEqual('abcdef<% out.print("g"); %>', execute_php(source))


class TestRFIPlugin(unittest.TestCase):

    def setUp(self):
        self.plugin = rfi()
        self.plugin.set_output(om.out)

    def configure(self, listen_address, listen_port, use_w3af_site):
        options = self.plugin.get_options()
        options["listen_address"].set_value(listen_address)
        options["listen_port"].set_value(listen_port)
        options["use_w3af_site"].set_value(use_w3af_site)
        self.plugin.set_options(options)

    def test_local_server_needs_an_address_when_w3af_site_is_disabled(self):
        with self.assertRaises(BaseFrameworkException):
            self.configure("", get_unused_port(), use_w3af_site=False)

    def test_running_local_server_is_a_valid_configuration(self):
        port = get_unused_port()
        webserver.start_webserver(LOCAL_ADDRESS, port, ".", om.out, RFIWebHandler)

        self.configure(LOCAL_ADDRESS, port, use_w3af_site=False)

        self.assertTrue(webserver.is_running(LOCAL_ADDRESS, port))

    def test_address_in_use_disables_the_local_server(self):
        with socket.socket() as busy_socket:
            busy_socket.bind((LOCAL_ADDRESS, 0))
            busy_socket.listen(1)
            busy_port = busy_socket.getsockname()[1]
            self.configure(LOCAL_ADDRESS, busy_port, use_w3af_site=True)
            request = FuzzableRequest(URL(f"{RFI_URL}rfi-rce.php?file=abc.txt"))

            self.plugin._local_test_inclusion(request, None, "address-in-use")

        self.assertIsNone(self.plugin._listen_address)

    def test_other_socket_errors_are_not_hidden(self):
        not_a_local_address = "203.0.113.77"
        self.configure(not_a_local_address, get_unused_port(), use_w3af_site=True)
        request = FuzzableRequest(URL(f"{RFI_URL}rfi-rce.php?file=abc.txt"))

        with self.assertRaises(OSError):
            self.plugin._local_test_inclusion(request, None, "address-not-local")

    def test_long_description_names_the_options(self):
        description = self.plugin.get_long_desc()

        for option in ("listen_address", "listen_port", "use_w3af_site"):
            self.assertIn(option, description)
