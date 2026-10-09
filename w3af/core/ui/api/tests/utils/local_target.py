"""
local_target.py

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

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

INDEX_PAGE = b"<html><head><title>target</title></head><body>w3af</body></html>"
MAX_HOLD_SECONDS = 60


class LocalTarget:
    """
    A local HTTP site to scan. The index page is answered right away while the
    other requests are held until release() is called, which keeps the scan
    running for as long as a test needs it.
    """

    def __init__(self) -> None:
        self.released = threading.Event()
        self.index_served = threading.Event()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), self._handler_class())
        self.server.daemon_threads = True
        self._thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.server.server_address[1]}/"

    def start(self) -> None:
        self._thread.start()

    def release(self) -> None:
        self.released.set()

    def close(self) -> None:
        self.release()
        self.server.shutdown()
        self.server.server_close()

    def _handler_class(self) -> type[BaseHTTPRequestHandler]:
        released = self.released
        index_served = self.index_served

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                if self.path != "/":
                    released.wait(MAX_HOLD_SECONDS)

                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.send_header("Content-Length", str(len(INDEX_PAGE)))
                self.end_headers()
                self.wfile.write(INDEX_PAGE)

                if self.path == "/":
                    index_served.set()

            def log_message(self, *args: object) -> None:
                """Keep the test output clean."""

        return Handler
