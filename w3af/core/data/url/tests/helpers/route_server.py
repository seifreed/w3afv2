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
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Self

HELPERS_DIR = os.path.dirname(os.path.abspath(__file__))
CERT_FILE = os.path.join(HELPERS_DIR, "unittest.crt")
KEY_FILE = os.path.join(HELPERS_DIR, "unittest.key")


@dataclass(frozen=True)
class RecordedRequest:
    method: str
    path: str
    headers: dict[str, str]
    body: bytes


@dataclass(frozen=True)
class Response:
    status: int = 200
    body: bytes | str = b""
    headers: list[tuple[str, str]] = field(default_factory=list)

    def body_bytes(self) -> bytes:
        if isinstance(self.body, str):
            return self.body.encode("utf-8")
        return self.body


Responder = Callable[[RecordedRequest], Response]
NOT_FOUND = Response(status=404, body="Not Found")
DEFAULT_CONTENT_TYPE = "text/plain; charset=utf-8"


def _fixed_responder(response: Response) -> Responder:
    def respond(_request: RecordedRequest) -> Response:
        return response

    return respond


class RouteServer:
    """
    Real HTTP(S) server bound to 127.0.0.1 on an ephemeral port. Responses are
    registered per (method, path) and every received request is recorded.
    """

    def __init__(self, use_tls: bool = False) -> None:
        self._use_tls = use_tls
        self._routes: dict[tuple[str, str], Responder] = {}
        self._requests: list[RecordedRequest] = []
        self._lock = threading.Lock()
        self._server = http.server.ThreadingHTTPServer(
            ("127.0.0.1", 0), self._build_handler_class()
        )
        self._server.daemon_threads = True
        if use_tls:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(CERT_FILE, KEY_FILE)
            self._server.socket = context.wrap_socket(
                self._server.socket,
                server_side=True,
                do_handshake_on_connect=False,
            )
        self._thread = threading.Thread(target=self._server.serve_forever)
        self._thread.daemon = True

    def __enter__(self) -> Self:
        self.start()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.stop()

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join()

    @property
    def port(self) -> int:
        return self._server.server_address[1]

    @property
    def base_url(self) -> str:
        scheme = "https" if self._use_tls else "http"
        return f"{scheme}://127.0.0.1:{self.port}"

    def url(self, path: str = "/") -> str:
        return self.base_url + path

    def add(self, method: str, path: str, response: Response | Responder) -> None:
        self._routes[(method, path)] = (
            _fixed_responder(response) if isinstance(response, Response) else response
        )

    @property
    def requests(self) -> list[RecordedRequest]:
        with self._lock:
            return list(self._requests)

    @property
    def last_request(self) -> RecordedRequest | None:
        with self._lock:
            return self._requests[-1] if self._requests else None

    def _record(self, request: RecordedRequest) -> None:
        with self._lock:
            self._requests.append(request)

    def _respond(self, request: RecordedRequest) -> Response:
        path_without_query = request.path.split("?", 1)[0]
        for key in (
            (request.method, request.path),
            (request.method, path_without_query),
        ):
            responder = self._routes.get(key)
            if responder is not None:
                return responder(request)
        return NOT_FOUND

    def _build_handler_class(self) -> type[http.server.BaseHTTPRequestHandler]:
        route_server = self

        class RouteHandler(http.server.BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def setup(self) -> None:
                if isinstance(self.request, ssl.SSLSocket):
                    self.request.do_handshake()
                super().setup()

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
                    method=self.command,
                    path=self.path,
                    headers={k.lower(): v for k, v in self.headers.items()},
                    body=body,
                )
                route_server._record(request)
                response = route_server._respond(request)
                payload = response.body_bytes()

                self.send_response(response.status)
                header_names = {name.lower() for name, _ in response.headers}
                for name, value in response.headers:
                    self.send_header(name, value)
                if "content-type" not in header_names:
                    self.send_header("Content-Type", DEFAULT_CONTENT_TYPE)
                if "content-length" not in header_names:
                    self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, format: str, *args: object) -> None:
                return None

        return RouteHandler
