"""
raw_handlers.py

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
import socketserver
import time


def closed_port():
    """
    :return: A TCP port on 127.0.0.1 where nothing is listening
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


class EmptyTCPHandler(socketserver.BaseRequestHandler):
    """Read the request and close the connection without answering."""

    def handle(self):
        self.data = self.request.recv(1024).strip()
        self.request.sendall(b"")


class TimeoutTCPHandler(socketserver.BaseRequestHandler):
    """Read the request and never answer it."""

    def handle(self):
        self.data = self.request.recv(1024).strip()
        time.sleep(60)
        self.request.sendall(b"")


class Ok200Handler(socketserver.BaseRequestHandler):
    body = "abc"

    def handle(self):
        self.data = self.request.recv(1024).strip()
        self.request.sendall(
            b"HTTP/1.0 200 Ok\r\n"
            b"Connection: Close\r\n"
            b"Content-Length: 3\r\n"
            b"\r\n" + self.body.encode()
        )
