"""
raw_server.py

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

import select
import socket
import socketserver
import threading

from w3af.core.data.url.tests.helpers.route_server import LOCALHOST, SOCKET_TIMEOUT


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
        return self._get_server().server_address[1]

    def _get_server(self) -> socketserver.ThreadingTCPServer:
        if self._server is None:
            raise RuntimeError("Raw server has not been started")
        return self._server

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
        server = self._get_server()
        if self._thread is None:
            raise RuntimeError("Raw server thread has not been started")
        server.shutdown()
        server.server_close()
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
