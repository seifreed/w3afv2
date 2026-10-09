"""
local_server.py

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

import os
import ssl
import threading
import unittest
from collections.abc import Callable
from dataclasses import dataclass, field
from email.message import Message
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Self
from urllib.parse import parse_qsl, urlsplit

HELPERS_DIR = os.path.dirname(__file__)
CERT_FILE = os.path.join(HELPERS_DIR, "unittest.crt")
KEY_FILE = os.path.join(HELPERS_DIR, "unittest.key")


@dataclass
class ReceivedRequest:
    method: str
    path: str
    headers: Message
    body: bytes
    # State shared by all the requests sent through the same TCP connection
    connection: dict = field(default_factory=dict)

    @property
    def route(self) -> str:
        return urlsplit(self.path).path


@dataclass
class Reply:
    status: int = 200
    body: bytes | str = b""
    headers: list[tuple[str, str]] = field(default_factory=list)
    content_type: str | None = "text/html; charset=utf-8"
    drop: bool = False

    def encoded_body(self) -> bytes:
        if isinstance(self.body, str):
            return self.body.encode("utf-8")
        return self.body


Responder = Callable[[ReceivedRequest], Reply]


def echo(request: ReceivedRequest) -> Reply:
    """
    Reply with the request line, the headers and every query string and
    url-encoded body parameter (decoded), one per line.
    """
    params = parse_qsl(urlsplit(request.path).query, keep_blank_values=True)
    params += parse_qsl(request.body.decode("utf-8"), keep_blank_values=True)

    lines = [f"{request.method} {request.path}"]
    lines += [f"{name}: {value}" for name, value in request.headers.items()]
    lines += [f"{name}={value}" for name, value in params]
    return Reply(200, "\n".join(lines))


class LocalServer:
    """
    A threaded HTTP (or HTTPS) server bound to a free port on 127.0.0.1.

    Requests are routed by path (query string excluded) to responders, which
    receive the parsed request and return a Reply. Every request is recorded
    in `requests` so tests can assert what the client really sent.
    """

    def __init__(self, routes: dict[str, Reply | Responder] | None = None, tls=False):
        self.routes: dict[str, Reply | Responder] = dict(routes or {})
        self.requests: list[ReceivedRequest] = []
        self.tls = tls
        self.server_names: list[str | None] = []

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), self._handler_class())
        self.server.daemon_threads = True

        if tls:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(certfile=CERT_FILE, keyfile=KEY_FILE)
            context.sni_callback = self._record_server_name
            self.server.socket = context.wrap_socket(
                self.server.socket, server_side=True
            )

        self._thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    @property
    def port(self) -> int:
        return self.server.server_address[1]

    def url(self, path="/", host="127.0.0.1") -> str:
        scheme = "https" if self.tls else "http"
        return f"{scheme}://{host}:{self.port}{path}"

    def start(self) -> Self:
        self._thread.start()
        return self

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()

    @classmethod
    def serve_for(cls, test_case: unittest.TestCase, routes=None, tls=False) -> Self:
        """
        Start a server which is closed when test_case finishes
        """
        server = cls(routes, tls=tls).start()
        test_case.addCleanup(server.close)
        return server

    def _record_server_name(self, ssl_socket, server_name, ssl_context):
        self.server_names.append(server_name)

    def _respond(self, request: ReceivedRequest) -> Reply:
        self.requests.append(request)

        responder = self.routes.get(request.route)
        if responder is None:
            return Reply(404, "Not found")

        if isinstance(responder, Reply):
            return responder

        return responder(request)

    def _handler_class(self) -> type[BaseHTTPRequestHandler]:
        respond = self._respond

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def setup(self) -> None:
                super().setup()
                self.connection_state: dict = {}

            def __getattr__(self, name):
                if name.startswith("do_"):
                    return self._dispatch
                raise AttributeError(name)

            def _dispatch(self) -> None:
                length = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(length) if length else b""

                request = ReceivedRequest(
                    self.command, self.path, self.headers, body, self.connection_state
                )
                reply = respond(request)
                if reply.drop:
                    # Close the connection without sending a response
                    self.close_connection = True
                    return

                payload = reply.encoded_body()

                self.send_response(reply.status)
                if reply.content_type is not None:
                    self.send_header("Content-Type", reply.content_type)
                for name, value in reply.headers:
                    self.send_header(name, value)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()

                if self.command != "HEAD":
                    self.wfile.write(payload)

            def log_message(self, *args: object) -> None:
                """Keep the test output clean."""

        return Handler
