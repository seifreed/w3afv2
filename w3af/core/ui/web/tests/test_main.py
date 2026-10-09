"""
test_main.py

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
import hashlib
import http.client
import io
import logging
import os
import shutil
import signal
import socket
import ssl
import sys
import tempfile
import threading
import time
import unittest
import webbrowser

from w3af.core.ui.api.tests.utils.api_unittest import AUTHORIZATION, PASSWORD
from w3af.core.ui.api.utils.digital_certificate import SSLCertificate
from w3af.core.ui.web.main import app, build_parser, main, ui_url

HOME_DIR_VARIABLE = "W3AF_HOME_DIR"
PASSWORD_HASH = hashlib.sha512(PASSWORD.encode()).hexdigest()
STARTUP_SECONDS = 30
NO_OP_BROWSER = "w3af-test-browser"


def free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


class UIClient(threading.Thread):
    """
    Request the web UI once the server answers, then interrupt the server the
    same way CTRL+C does.
    """

    def __init__(self, port, context=None):
        super().__init__(daemon=True)
        self.port = port
        self.context = context
        self.body = None

    def run(self):
        deadline = time.monotonic() + STARTUP_SECONDS
        try:
            while self.body is None and time.monotonic() < deadline:
                self.body = self.fetch()
        finally:
            signal.raise_signal(signal.SIGINT)

    def connection(self):
        if self.context is None:
            return http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        return http.client.HTTPSConnection(
            "127.0.0.1", self.port, timeout=5, context=self.context
        )

    def fetch(self):
        connection = self.connection()
        try:
            connection.request(
                "GET", "/ui/", headers={"Authorization": f"Basic {AUTHORIZATION}"}
            )
            return connection.getresponse().read().decode("utf-8")
        except OSError:
            time.sleep(0.1)
            return None
        finally:
            connection.close()


class WebMainTest(unittest.TestCase):
    def setUp(self):
        self.config = dict(app.config)
        self.root_level = logging.getLogger().level
        self.previous_home = os.environ.get(HOME_DIR_VARIABLE)
        self.home = tempfile.mkdtemp(prefix="w3af-home-")
        os.environ[HOME_DIR_VARIABLE] = self.home

    def tearDown(self):
        app.config.clear()
        app.config.update(self.config)
        logging.getLogger().setLevel(self.root_level)
        if self.previous_home is None:
            os.environ.pop(HOME_DIR_VARIABLE)
        else:
            os.environ[HOME_DIR_VARIABLE] = self.previous_home
        shutil.rmtree(self.home)

    def run_main(self, *argv):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            exit_code = main(list(argv))
        return exit_code, output.getvalue()

    def serve_once(self, client, *argv):
        client.start()
        exit_code, output = self.run_main(*argv)
        client.join(STARTUP_SECONDS)
        return exit_code, output

    def test_build_parser_adds_browser_option(self):
        parser = build_parser()

        self.assertTrue(parser.parse_args(["--no-browser"]).no_browser)
        self.assertFalse(parser.parse_args([]).no_browser)
        self.assertEqual(parser.description, "Web user interface for w3af")

    def test_ui_url(self):
        self.assertEqual(ui_url("127.0.0.1", 5000, False), "http://127.0.0.1:5000/ui/")
        self.assertEqual(ui_url("::1", 8443, True), "https://[::1]:8443/ui/")

    def test_invalid_arguments(self):
        exit_code, output = self.run_main("127.0.0.1:http")

        self.assertEqual(exit_code, 1)
        self.assertIn("Invalid port number", output)

    def test_address_that_can_not_be_bound(self):
        with self.assertRaises(SystemExit) as exit_context:
            self.run_main("192.0.2.1:8080", "--no-ssl", "--no-browser")

        self.assertEqual(exit_context.exception.code, 1)

    def test_serves_the_ui_until_interrupted(self):
        port = free_port()
        url = f"http://127.0.0.1:{port}/ui/"

        client = UIClient(port)
        exit_code, output = self.serve_once(
            client,
            f"127.0.0.1:{port}",
            "--no-ssl",
            "--no-browser",
            "-v",
            "-p",
            PASSWORD_HASH,
        )

        self.assertEqual(exit_code, 0)
        self.assertIn(f"available at {url}", output)
        self.assertIn("The w3af web user interface was stopped.", output)
        self.assertIn('id="scan-form"', client.body)

    def test_serves_the_ui_over_https_and_opens_the_browser(self):
        no_op = webbrowser.GenericBrowser([sys.executable, "-c", "pass"])
        webbrowser.register(NO_OP_BROWSER, None, no_op, preferred=True)
        port = free_port()
        url = f"https://127.0.0.1:{port}/ui/"
        cert_path, _ = SSLCertificate().get_cert_key("127.0.0.1")

        client = UIClient(port, ssl.create_default_context(cafile=cert_path))
        exit_code, output = self.serve_once(
            client, f"127.0.0.1:{port}", "-p", PASSWORD_HASH
        )

        self.assertEqual(exit_code, 0)
        self.assertIn(f"available at {url}", output)
        self.assertIn('id="scan-form"', client.body)
