"""
route_server.py

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

import http.server
import os
import ssl
import threading
import unittest
from collections.abc import Callable
from dataclasses import dataclass, field
from email.message import Message
from typing import Self
from urllib.parse import parse_qsl, urlsplit

HELPERS_DIR = os.path.dirname(os.path.abspath(__file__))
CERT_FILE = os.path.join(HELPERS_DIR, "unittest.crt")
KEY_FILE = os.path.join(HELPERS_DIR, "unittest.key")

LOCALHOST = "127.0.0.1"
SOCKET_TIMEOUT = 10
DEFAULT_CONTENT_TYPE = "text/html; charset=utf-8"


@dataclass(frozen=True)
class RecordedRequest:
    method: str
    path: str
    headers: Message
    body: bytes
    # State shared by every request sent through the same TCP connection
    connection: dict = field(default_factory=dict, compare=False)

    @property
    def route(self) -> str:
        return urlsplit(self.path).path


@dataclass(frozen=True)
class Response:
    """
    What the server answers. `raw` bytes are written to the socket verbatim
    instead of building a response; `close` closes the connection after the
    response and `drop` closes it without answering.
    """

    status: int = 200
    body: bytes | str = b""
    headers: list[tuple[str, str]] = field(default_factory=list)
    content_type: str | None = DEFAULT_CONTENT_TYPE
    raw: bytes | None = None
    close: bool = False
    drop: bool = False

    def body_bytes(self) -> bytes:
        if isinstance(self.body, str):
            return self.body.encode("utf-8")
        return self.body


Responder = Callable[[RecordedRequest], Response]
Route = Response | Responder
NOT_FOUND = Response(status=404, body="Not Found")


def echo(request: RecordedRequest) -> Response:
    """
    Answer with the request line, the headers and every query string and
    url-encoded body parameter (decoded), one per line.
    """
    params = parse_qsl(urlsplit(request.path).query, keep_blank_values=True)
    params += parse_qsl(request.body.decode("utf-8"), keep_blank_values=True)

    lines = [f"{request.method} {request.path}"]
    lines += [f"{name}: {value}" for name, value in request.headers.items()]
    lines += [f"{name}={value}" for name, value in params]
    return Response(200, "\n".join(lines))


def default_tls_context() -> ssl.SSLContext:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(CERT_FILE, KEY_FILE)
    return context


class _Server(http.server.ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):
        """Clients that hang up early are expected, keep the output clean."""


class RouteServer:
    """
    Real HTTP(S) server bound to 127.0.0.1 on an ephemeral port.

    `routes` maps a path (with or without the query string) to a Response, or
    to a callable receiving the RecordedRequest, for every HTTP method;
    add() registers a route for a single method, which takes precedence.
    Unknown paths get a 404 and every request is recorded in `requests`.
    """

    def __init__(
        self,
        routes: dict[str, Route] | None = None,
        use_tls: bool = False,
        tls_context: ssl.SSLContext | None = None,
    ) -> None:
        self.routes: dict[str, Route] = dict(routes or {})
        self._method_routes: dict[tuple[str, str], Route] = {}
        self._requests: list[RecordedRequest] = []
        self._lock = threading.Lock()
        self.server_names: list[str | None] = []

        if use_tls and tls_context is None:
            tls_context = default_tls_context()
        self._use_tls = tls_context is not None

        self._server = _Server((LOCALHOST, 0), self._build_handler_class())
        if tls_context is not None:
            tls_context.sni_callback = self._record_server_name
            self._server.socket = tls_context.wrap_socket(
                self._server.socket,
                server_side=True,
                do_handshake_on_connect=False,
            )
        self._thread = threading.Thread(target=self._server.serve_forever)
        self._thread.daemon = True

    @classmethod
    def serve_for(
        cls, test_case: unittest.TestCase, routes=None, use_tls=False
    ) -> Self:
        """
        :return: A started server that is stopped when test_case finishes
        """
        server = cls(routes, use_tls=use_tls).start()
        test_case.addCleanup(server.stop)
        return server

    def __enter__(self) -> Self:
        return self.start()

    def __exit__(self, *exc_info: object) -> None:
        self.stop()

    def start(self) -> Self:
        self._thread.start()
        return self

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(SOCKET_TIMEOUT)

    @property
    def port(self) -> int:
        return self._server.server_address[1]

    @property
    def netloc(self) -> str:
        return f"{LOCALHOST}:{self.port}"

    @property
    def base_url(self) -> str:
        scheme = "https" if self._use_tls else "http"
        return f"{scheme}://{self.netloc}"

    def url(self, path: str = "/", host: str = LOCALHOST) -> str:
        scheme = "https" if self._use_tls else "http"
        return f"{scheme}://{host}:{self.port}{path}"

    def add(self, method: str, path: str, response: Route) -> None:
        self._method_routes[(method, path)] = response

    @property
    def requests(self) -> list[RecordedRequest]:
        with self._lock:
            return list(self._requests)

    @property
    def last_request(self) -> RecordedRequest | None:
        with self._lock:
            return self._requests[-1] if self._requests else None

    def _record_server_name(self, ssl_socket, server_name, ssl_context):
        self.server_names.append(server_name)

    def _respond(self, request: RecordedRequest) -> Response:
        with self._lock:
            self._requests.append(request)

        for path in (request.path, request.route):
            route = self._method_routes.get((request.method, path))
            if route is None:
                route = self.routes.get(path)
            if route is not None:
                return route if isinstance(route, Response) else route(request)
        return NOT_FOUND

    def _build_handler_class(self) -> type[http.server.BaseHTTPRequestHandler]:
        route_server = self

        class RouteHandler(http.server.BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def setup(self) -> None:
                if isinstance(self.request, ssl.SSLSocket):
                    self.request.do_handshake()
                super().setup()
                self.connection_state: dict = {}

            def handle(self) -> None:
                try:
                    super().handle()
                except (ssl.SSLError, ConnectionError):
                    self.close_connection = True

            def handle_one_request(self) -> None:
                self.raw_requestline = self.rfile.readline(65537)
                if not self.raw_requestline:
                    self.close_connection = True
                    return
                if not self.parse_request():
                    return
                self._serve()
                self.wfile.flush()

            def _serve(self) -> None:
                length = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(length) if length else b""
                request = RecordedRequest(
                    self.command, self.path, self.headers, body, self.connection_state
                )
                response = route_server._respond(request)

                if response.drop:
                    self.close_connection = True
                    return

                if response.raw is not None:
                    self.wfile.write(response.raw)
                    self.close_connection = True
                    return

                payload = response.body_bytes()
                self.send_response(response.status)
                header_names = {name.lower() for name, _ in response.headers}
                for name, value in response.headers:
                    self.send_header(name, value)
                if (
                    response.content_type is not None
                    and "content-type" not in header_names
                ):
                    self.send_header("Content-Type", response.content_type)
                if "content-length" not in header_names:
                    self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                if self.command != "HEAD":
                    self.wfile.write(payload)
                if response.close:
                    self.close_connection = True

            def log_message(self, format: str, *args: object) -> None:
                return None

        return RouteHandler
