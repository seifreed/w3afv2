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

import json
import ssl

from w3af.core.ui.api.main import main
from w3af.core.ui.api.tests.utils.server_harness import (
    PASSWORD_HASH,
    InterruptingClient,
    ServerMainTestCase,
    free_port,
)
from w3af.core.ui.api.utils.digital_certificate import SSLCertificate
from w3af.core.ui.api.utils.mp_flask import server_url


class APIMainTest(ServerMainTestCase):
    """
    Run the real REST API entry point on a local port, query it and stop it
    the same way CTRL+C does.
    """

    entry_point = staticmethod(main)

    def test_server_url(self):
        self.assertEqual(server_url("127.0.0.1", 5000, False), "http://127.0.0.1:5000")
        self.assertEqual(server_url("::1", 8443, True), "https://[::1]:8443")

    def test_invalid_arguments(self):
        exit_code, output = self.run_main("127.0.0.1:http")

        self.assertEqual(exit_code, 1)
        self.assertIn("Invalid port number", output)

    def test_address_that_can_not_be_bound(self):
        with self.assertRaises(SystemExit) as exit_context:
            self.run_main("192.0.2.1:8080", "--no-ssl")

        self.assertEqual(exit_context.exception.code, 1)

    def test_serves_the_api_until_interrupted(self):
        port = free_port()

        client = InterruptingClient(port, "/")
        exit_code, output = self.serve_once(
            client, f"127.0.0.1:{port}", "--no-ssl", "-v", "-p", PASSWORD_HASH
        )

        self.assertEqual(exit_code, 0)
        self.assertIn(f"w3af REST API available at http://127.0.0.1:{port}/", output)
        self.assertIn("The w3af REST API was stopped.", output)
        self.assertIn("docs", json.loads(client.get_body()))

    def test_serves_the_api_over_https(self):
        port = free_port()
        cert_path, _ = SSLCertificate().get_cert_key("127.0.0.1")

        client = InterruptingClient(
            port, "/", ssl.create_default_context(cafile=cert_path)
        )
        exit_code, output = self.serve_once(
            client, f"127.0.0.1:{port}", "-p", PASSWORD_HASH
        )

        self.assertEqual(exit_code, 0)
        self.assertIn(f"w3af REST API available at https://127.0.0.1:{port}/", output)
        self.assertIn("docs", json.loads(client.get_body()))
