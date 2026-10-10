"""
local_tls_server.py

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

import socketserver
import ssl
import threading

REQUEST_SIZE = 65536
CLIENT_TIMEOUT = 5

HTTP_RESPONSE = (
    b"HTTP/1.1 200 Ok\r\n"
    b"Connection: close\r\n"
    b"Content-Type: text/html\r\n"
    b"Content-Length: 3\r\n\r\nabc"
)


class TlsHandler(socketserver.BaseRequestHandler):
    """
    Completes the TLS handshake, reads the request and answers with a fixed
    HTTP response. The clients of these tests abort handshakes and connections
    on purpose, so any connection error ends the connection and nothing else.
    """

    def handle(self):
        self.request.settimeout(CLIENT_TIMEOUT)

        try:
            with self.server.tls_context.wrap_socket(
                self.request, server_side=True
            ) as tls_socket:
                if tls_socket.recv(REQUEST_SIZE):
                    tls_socket.sendall(HTTP_RESPONSE)
        except (ssl.SSLError, OSError):
            return


class LocalTlsServer(socketserver.ThreadingTCPServer):
    """
    A threaded TLS server listening on a free local port.
    """

    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, bundle_path):
        super().__init__(("127.0.0.1", 0), TlsHandler)
        self.tls_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.tls_context.load_cert_chain(certfile=bundle_path)
        self._thread = threading.Thread(target=self.serve_forever, daemon=True)

    @property
    def port(self):
        return self.server_address[1]

    def start(self):
        self._thread.start()

    def stop(self):
        self.shutdown()
        self.server_close()
        self._thread.join()
