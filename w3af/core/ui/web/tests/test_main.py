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

import ssl
import sys
import webbrowser

from w3af.core.ui.api.tests.utils.server_harness import (
    PASSWORD_HASH,
    InterruptingClient,
    ServerMainTestCase,
    free_port,
)
from w3af.core.ui.api.utils.digital_certificate import SSLCertificate
from w3af.core.ui.web.main import build_parser, main, ui_url

NO_OP_BROWSER = "w3af-test-browser"


class WebMainTest(ServerMainTestCase):
    entry_point = staticmethod(main)

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

        client = InterruptingClient(port, "/ui/")
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
        self.assertIn('id="scan-form"', client.get_body())

    def test_serves_the_ui_over_https_and_opens_the_browser(self):
        no_op = webbrowser.GenericBrowser([sys.executable, "-c", "pass"])
        webbrowser.register(NO_OP_BROWSER, None, no_op, preferred=True)
        port = free_port()
        url = f"https://127.0.0.1:{port}/ui/"
        cert_path, _ = SSLCertificate().get_cert_key("127.0.0.1")

        client = InterruptingClient(
            port, "/ui/", ssl.create_default_context(cafile=cert_path)
        )
        exit_code, output = self.serve_once(
            client, f"127.0.0.1:{port}", "-p", PASSWORD_HASH
        )

        self.assertEqual(exit_code, 0)
        self.assertIn(f"available at {url}", output)
        self.assertIn('id="scan-form"', client.get_body())
