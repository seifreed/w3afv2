"""
local_server.py

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

In-process HTTP(S) servers and an HTTP CONNECT proxy used by the URL handler
tests, so they never depend on external hosts or the moth test server.
"""

import datetime
import ipaddress
import select
import socket
import socketserver
import ssl
import tempfile
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from email.message import Message
from functools import cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

LOCALHOST = "127.0.0.1"
SOCKET_TIMEOUT = 10


@dataclass
class Reply:
    """
    What the server answers. When `raw` is set those bytes are written to the
    socket verbatim instead of building a response.
    """

    code: int = 200
    body: bytes | str = b""
    headers: list[tuple[str, str]] = field(default_factory=list)
    raw: bytes | None = None
    close: bool = False


@dataclass
class RecordedRequest:
    method: str
    path: str
    headers: Message
    body: bytes


Route = Reply | Callable[[RecordedRequest], Reply]


@dataclass(frozen=True)
class Certificate:
    cert_file: Path
    key_file: Path
    certificate: x509.Certificate


@cache
def certificate(common_name="localhost", with_san=True):
    """
    :return: A self-signed certificate (and key) stored in a temporary
             directory that lives as long as the test process.
    """
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, common_name)] if common_name else []
    )
    now = datetime.datetime.now(datetime.UTC)
    builder = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=30))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), True)
    )
    if with_san:
        builder = builder.add_extension(
            x509.SubjectAlternativeName(
                [
                    x509.DNSName("localhost"),
                    x509.IPAddress(ipaddress.ip_address(LOCALHOST)),
                ]
            ),
            False,
        )
    cert = builder.sign(key, hashes.SHA256())

    directory = Path(tempfile.mkdtemp(prefix="w3af-test-cert-"))
    cert_file = directory / "cert.pem"
    key_file = directory / "key.pem"
    cert_file.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_file.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    return Certificate(cert_file, key_file, cert)


def server_tls_context(cert=None):
    cert = cert or certificate()
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert.cert_file, cert.key_file)
    return context


class _RequestHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass

    def handle_one_request(self):
        try:
            super().handle_one_request()
        except (OSError, ssl.SSLError):
            self.close_connection = True

    def __getattr__(self, name):
        # Answer every HTTP method (do_GET, do_POST, do_FOO...) the same way
        if name.startswith("do_"):
            return self._dispatch
        raise AttributeError(name)

    def _dispatch(self):
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""
        request = RecordedRequest(self.command, self.path, self.headers, body)
        owner = self.server.owner
        owner.requests.append(request)
        self._send(owner.reply_for(request))

    def _send(self, reply):
        if reply.raw is not None:
            self.wfile.write(reply.raw)
            self.wfile.flush()
            self.close_connection = True
            return

        body = reply.body.encode("utf-8") if isinstance(reply.body, str) else reply.body
        self.send_response(reply.code)
        names = {name.lower() for name, _ in reply.headers}
        for name, value in reply.headers:
            self.send_header(name, value)
        if "content-type" not in names:
            self.send_header("Content-Type", "text/html; charset=utf-8")
        if "content-length" not in names:
            self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)
        self.wfile.flush()
        if reply.close:
            self.close_connection = True


class _Server(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):
        pass


class LocalServer:
    """
    A threaded HTTP server on 127.0.0.1 that answers from a route table:

        with LocalServer({"/": Reply(body="hello")}) as server:
            urlopen(server.url("/"))

    Routes map a path (with or without the query string) to a Reply or to a
    callable receiving the RecordedRequest. Unknown paths get a 404.
    """

    def __init__(self, routes=None, tls=False, tls_context=None) -> None:
        self.routes: dict[str, Route] = dict(routes or {})
        self.requests: list[RecordedRequest] = []
        self.scheme = "https" if tls or tls_context else "http"
        self._tls_context = tls_context or (server_tls_context() if tls else None)
        self._server = None
        self._thread = None

    def reply_for(self, request):
        route = self.routes.get(request.path)
        if route is None:
            route = self.routes.get(request.path.split("?", 1)[0])
        if route is None:
            return Reply(404, "not found")
        return route(request) if callable(route) else route

    @property
    def port(self):
        return self._server.server_address[1]

    @property
    def netloc(self):
        return f"{LOCALHOST}:{self.port}"

    def url(self, path="/"):
        return f"{self.scheme}://{self.netloc}{path}"

    def start(self):
        self._server = _Server((LOCALHOST, 0), _RequestHandler)
        self._server.owner = self
        if self._tls_context is not None:
            self._server.socket = self._tls_context.wrap_socket(
                self._server.socket, server_side=True, do_handshake_on_connect=False
            )
        self._thread = threading.Thread(target=self._server.serve_forever)
        self._thread.daemon = True
        self._thread.start()
        return self

    def stop(self):
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(SOCKET_TIMEOUT)

    def __enter__(self):
        return self.start()

    def __exit__(self, *exc_info):
        self.stop()


class RawServer:
    """
    A TCP server on 127.0.0.1 that hands every accepted socket to `handler`,
    for tests that need byte-level control (half-written TLS, resets, ...).
    """

    def __init__(self, handler):
        self.handler = handler
        self.connections = 0
        self._server = None
        self._thread = None

    @property
    def port(self):
        return self._server.server_address[1]

    def start(self):
        owner = self

        class Handler(socketserver.BaseRequestHandler):
            def handle(self):
                owner.connections += 1
                self.request.settimeout(SOCKET_TIMEOUT)
                try:
                    owner.handler(self.request)
                except OSError:
                    pass

        self._server = socketserver.ThreadingTCPServer((LOCALHOST, 0), Handler)
        self._server.daemon_threads = True
        self._thread = threading.Thread(target=self._server.serve_forever)
        self._thread.daemon = True
        self._thread.start()
        return self

    def stop(self):
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(SOCKET_TIMEOUT)

    def __enter__(self):
        return self.start()

    def __exit__(self, *exc_info):
        self.stop()


def read_http_head(sock):
    """
    :return: The bytes of an HTTP request head (up to the empty line)
    """
    data = b""
    while b"\r\n\r\n" not in data:
        chunk = sock.recv(4096)
        if not chunk:
            break
        data += chunk
    return data


class ConnectProxy(RawServer):
    """
    An HTTP CONNECT proxy: it tunnels to the requested host:port, unless the
    target is listed in `refuse` in which case it answers 407.
    """

    def __init__(self, refuse=()):
        super().__init__(self._tunnel)
        self.refuse = set(refuse)
        self.targets = []

    def _tunnel(self, client):
        head = read_http_head(client).decode("ascii")
        target = head.split(" ", 2)[1]
        self.targets.append(target)

        if target in self.refuse:
            client.sendall(b"HTTP/1.1 407 Proxy Authentication Required\r\n\r\n")
            return

        host, port = target.rsplit(":", 1)
        upstream = socket.create_connection((host, int(port)), SOCKET_TIMEOUT)
        client.sendall(b"HTTP/1.1 200 Connection established\r\nX-Proxy: local\r\n\r\n")
        with upstream:
            sockets = [client, upstream]
            while True:
                readable, _, _ = select.select(sockets, [], [], SOCKET_TIMEOUT)
                if not readable:
                    return
                for source in readable:
                    data = source.recv(65536)
                    if not data:
                        return
                    (upstream if source is client else client).sendall(data)
