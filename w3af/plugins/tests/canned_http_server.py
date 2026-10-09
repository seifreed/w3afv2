"""
canned_http_server.py

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

import json
import os
import ssl
import sys
import threading
import urllib.parse
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import NamedTuple

from w3af import ROOT_PATH

CERT_DIR = os.path.join(ROOT_PATH, "core", "data", "url", "tests", "helpers")
CERT_FILE = os.path.join(CERT_DIR, "unittest.crt")
KEY_FILE = os.path.join(CERT_DIR, "unittest.key")

FRAMING_HEADERS = {"status", "content-length", "transfer-encoding"}


class CannedRequest:
    """
    An HTTP request received by the CannedHTTPServer, exposing the request
    line, headers and body to the responder.
    """

    def __init__(self, command, uri, headers, body):
        self.command = command
        self.uri = uri
        self.headers = headers
        self.body = body

    def __repr__(self):
        return f"<CannedRequest {self.command} {self.uri}>"

    @property
    def path(self):
        split_uri = urllib.parse.urlsplit(self.uri)
        if split_uri.query:
            return f"{split_uri.path}?{split_uri.query}"
        return split_uri.path

    @property
    def parsed_body(self):
        text = self.body.decode("utf-8", errors="replace")
        try:
            return json.loads(text)
        except ValueError:
            return urllib.parse.parse_qs(text)


class CannedReply(NamedTuple):
    status: int
    headers: dict
    body: str | bytes
    reason: str | None = None


Responder = Callable[[CannedRequest], CannedReply]


class CannedRequestHandler(BaseHTTPRequestHandler):
    """
    Acts as an HTTP proxy for the scanned site: requests arrive with absolute
    URIs (or inside a CONNECT tunnel for HTTPS) and are answered by the
    server's responder, so the scanner keeps the original target URLs.
    """

    protocol_version = "HTTP/1.1"
    server: "CannedHTTPServer"
    tunnel_origin: str | None = None

    def __getattr__(self, name):
        if name.startswith("do_"):
            return self.serve_canned_response
        raise AttributeError(name)

    def log_message(self, format, *args):
        return

    def do_CONNECT(self):
        self.send_response(200, "Connection established")
        self.end_headers()

        tls_socket = self.server.tls_context.wrap_socket(
            self.connection, server_side=True
        )
        self.request = self.connection = tls_socket
        self.setup()
        self.tunnel_origin = f"https://{self._tunnel_authority()}"
        self.close_connection = False

    def _tunnel_authority(self):
        host, _, port = self.path.rpartition(":")
        if port == "443":
            return host
        return self.path

    def serve_canned_response(self):
        request = CannedRequest(
            self.command, self._absolute_uri(), self.headers, self._read_body()
        )
        self.server.requests.append(request)

        self._write_reply(self.server.responder(request))

    def _absolute_uri(self):
        if urllib.parse.urlsplit(self.path).scheme:
            return self.path

        origin = self.tunnel_origin or f"http://{self.headers.get('Host', '')}"
        return origin + self.path

    def _read_body(self):
        length = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(length) if length else b""

    def _write_reply(self, reply):
        body = reply.body
        if isinstance(body, str):
            body = body.encode("utf-8")

        # Like send_response(), but a canned Server or Date header replaces
        # the default one instead of being sent twice
        self.send_response_only(reply.status, reply.reason)
        canned_names = {name.lower() for name in reply.headers}
        if "server" not in canned_names:
            self.send_header("Server", self.version_string())
        if "date" not in canned_names:
            self.send_header("Date", self.date_time_string())

        for name, value in reply.headers.items():
            if name.lower() not in FRAMING_HEADERS:
                self.send_header(name, str(value))
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()

        if self.command != "HEAD":
            self.wfile.write(body)


class CannedHTTPServer(ThreadingHTTPServer):
    """
    A real HTTP server listening on an ephemeral 127.0.0.1 port which answers
    every request using the provided responder callable.
    """

    daemon_threads = True
    request_queue_size = 128

    def __init__(self, responder: Responder):
        super().__init__(("127.0.0.1", 0), CannedRequestHandler)
        self.responder = responder
        self.requests: list[CannedRequest] = []
        self.tls_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.tls_context.load_cert_chain(CERT_FILE, KEY_FILE)
        self._thread = threading.Thread(target=self.serve_forever, daemon=True)

    @property
    def host(self):
        return self.server_address[0]

    @property
    def port(self):
        return self.server_address[1]

    def handle_error(self, request, client_address):
        if isinstance(sys.exception(), ConnectionError):
            return
        super().handle_error(request, client_address)

    def start(self):
        self._thread.start()

    def stop(self):
        self.shutdown()
        self.server_close()
        self._thread.join()
