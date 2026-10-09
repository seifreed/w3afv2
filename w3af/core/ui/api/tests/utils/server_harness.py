"""
server_harness.py

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

import contextlib
import hashlib
import http.client
import io
import logging
import signal
import socket
import threading
import time
import unittest
from collections.abc import Callable, Sequence

from w3af.core.ui.api import app
from w3af.core.ui.api.tests.utils.api_unittest import AUTHORIZATION, PASSWORD
from w3af.tests.helpers.home_dir import use_temporary_home

STARTUP_SECONDS = 30
PASSWORD_HASH = hashlib.sha512(PASSWORD.encode()).hexdigest()


def free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


class InterruptingClient(threading.Thread):
    """
    Request a path once the server answers, then interrupt the server the
    same way CTRL+C does.
    """

    def __init__(self, port, path, context=None):
        super().__init__(daemon=True)
        self.port = port
        self.path = path
        self.context = context
        self.body = None

    def run(self):
        deadline = time.monotonic() + STARTUP_SECONDS
        try:
            while self.body is None and time.monotonic() < deadline:
                self.body = self.fetch()
        finally:
            signal.raise_signal(signal.SIGINT)

    def connection(self):
        if self.context is None:
            return http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        return http.client.HTTPSConnection(
            "127.0.0.1", self.port, timeout=5, context=self.context
        )

    def fetch(self):
        connection = self.connection()
        try:
            connection.request(
                "GET",
                self.path,
                headers={"Authorization": f"Basic {AUTHORIZATION}"},
            )
            return connection.getresponse().read().decode("utf-8")
        except OSError:
            time.sleep(0.1)
            return None
        finally:
            connection.close()


class ServerMainTestCase(unittest.TestCase):
    """
    Run a server entry point (its real main(), set as the entry_point
    staticmethod by subclasses) in a temporary w3af home directory, restoring
    the shared Flask app configuration afterwards.
    """

    entry_point: Callable[[Sequence[str]], int]

    def setUp(self):
        self.config = dict(app.config)
        self.root_level = logging.getLogger().level
        self.home = use_temporary_home(self)

    def tearDown(self):
        app.config.clear()
        app.config.update(self.config)
        logging.getLogger().setLevel(self.root_level)

    def run_main(self, *argv):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            exit_code = self.entry_point(list(argv))
        return exit_code, output.getvalue()

    def serve_once(self, client, *argv):
        client.start()
        exit_code, output = self.run_main(*argv)
        client.join(STARTUP_SECONDS)
        return exit_code, output
