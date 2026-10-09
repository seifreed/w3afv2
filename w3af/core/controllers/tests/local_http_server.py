"""
local_http_server.py

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
import ssl
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import TracebackType
from typing import Self

LOCALHOST = "127.0.0.1"


@dataclass
class Reply:
    status: int = 200
    body: str | bytes = ""
    headers: dict[str, str] = field(default_factory=dict)


Responder = Callable[[str, str], Reply]


class LocalHTTPServer:
    """
    A real HTTP server listening on an ephemeral 127.0.0.1 port. Every request
    is answered with the Reply built by the responder, which receives the HTTP
    method and the request path (including the query string).

    close() waits for every request handler thread, so no server thread is
    left alive after it returns.
    """

    def __init__(
        self, responder: Responder, tls_cert_and_key: tuple[str, str] | None = None
    ) -> None:
        """
        :param responder: Builds the reply for each request
        :param tls_cert_and_key: Paths to the certificate and private key files
                                 to serve HTTPS instead of HTTP
        """
        self.requested_paths: list[str] = []
        self._server = ThreadingHTTPServer(
            (LOCALHOST, 0), self._handler_class(responder)
        )
        self._scheme = "http"

        if tls_cert_and_key is not None:
            self._serve_tls(*tls_cert_and_key)

        self._server.daemon_threads = False
        self._server.block_on_close = True
        self._thread = threading.Thread(
            target=self._server.serve_forever, name="LocalHTTPServer", daemon=True
        )

    def _serve_tls(self, certfile: str, keyfile: str) -> None:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(certfile, keyfile)
        self._server.socket = context.wrap_socket(self._server.socket, server_side=True)
        self._scheme = "https"

    @property
    def port(self) -> int:
        return int(self._server.server_address[1])

    def url(self, path: str = "/") -> str:
        return f"{self._scheme}://{LOCALHOST}:{self.port}{path}"

    def start(self) -> Self:
        self._thread.start()
        return self

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join()

    def __enter__(self) -> Self:
        return self.start()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def _handler_class(self, responder: Responder) -> type[BaseHTTPRequestHandler]:
        requested_paths = self.requested_paths

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                self._reply("GET")

            def do_POST(self) -> None:
                self._reply("POST")

            def do_HEAD(self) -> None:
                self._reply("HEAD")

            def _reply(self, method: str) -> None:
                requested_paths.append(self.path)
                reply = responder(method, self.path)
                body = reply.body
                if isinstance(body, str):
                    body = body.encode("utf-8")

                self.send_response(reply.status)
                headers = {"Content-Type": "text/html", **reply.headers}
                for name, value in headers.items():
                    self.send_header(name, value)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()

                if method != "HEAD":
                    self.wfile.write(body)

            def log_message(self, *args: object) -> None:
                """Keep the test output clean."""

        return Handler


def closed_local_port() -> int:
    """
    :return: A 127.0.0.1 port where nothing is listening, connections to it
             are refused by the operating system.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((LOCALHOST, 0))
        return int(sock.getsockname()[1])
