"""
test_webserver.py

Copyright 2012 Andres Riancho

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

import http.client
import os
import shutil
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

from w3af.core.controllers.daemons.webserver import (
    HTTPServer,
    WebHandler,
    is_running,
    start_webserver,
)
from w3af.core.controllers.misc.get_unused_port import get_unused_port

IP = "127.0.0.1"
TEST_STRING = "abc<>def"
SHUTDOWN_TIMEOUT = 10


class FailingHandler(WebHandler):
    def do_GET(self):
        raise RuntimeError("handler failure")


def wait_until_down(server):
    for _ in range(SHUTDOWN_TIMEOUT * 10):
        if server.is_down():
            return True
        threading.Event().wait(0.1)
    return False


class TestWebserver(unittest.TestCase):

    def setUp(self):
        self.webroot = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.webroot)

        self.port = get_unused_port()
        self.server = start_webserver(IP, self.port, self.webroot)

    def url(self, path):
        return f"http://{IP}:{self.port}/{path}"

    def create_file(self, name):
        with open(os.path.join(self.webroot, name), "w") as test_fh:
            test_fh.write(TEST_STRING)

    def test_get_404(self):
        with self.assertRaises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(self.url("missing.txt"))

        self.assertEqual(error.exception.code, 404)

    def test_get_path_traversal_403(self):
        connection = http.client.HTTPConnection(IP, self.port)
        connection.request("GET", "/../etc/passwd")

        self.assertEqual(connection.getresponse().status, 403)
        connection.close()

    def test_get_exists_with_known_content_type(self):
        self.create_file("foofile.txt")

        response = urllib.request.urlopen(self.url("foofile.txt"))

        self.assertEqual(response.read().decode("utf-8"), TEST_STRING)
        self.assertEqual(response.headers["Content-type"], "text/plain")

    def test_get_exists_with_unknown_content_type(self):
        self.create_file("foofile.w3afunknown")

        response = urllib.request.urlopen(self.url("foofile.w3afunknown"))

        self.assertEqual(response.read().decode("utf-8"), TEST_STRING)
        self.assertEqual(response.headers["Content-type"], "text/html")

    def test_is_running(self):
        self.assertFalse(self.server.is_down())
        self.assertTrue(is_running(IP, self.port))

    def test_is_running_unknown_address(self):
        self.assertFalse(is_running(IP, get_unused_port()))

    def test_start_webserver_returns_running_instance(self):
        self.assertIs(start_webserver(IP, self.port, self.webroot), self.server)

    def test_idle_server_shuts_down_and_restarts(self):
        self.assertTrue(wait_until_down(self.server))
        self.assertFalse(is_running(IP, self.port))

        restarted = start_webserver(IP, self.port, self.webroot)

        self.assertIsNot(restarted, self.server)
        self.assertTrue(is_running(IP, self.port))

    def test_get_port(self):
        self.assertEqual(self.server.get_port(), self.port)


class TestWebserverHandlerError(unittest.TestCase):

    def test_handler_exception_is_logged(self):
        server = HTTPServer((IP, 0), tempfile.gettempdir(), FailingHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        logger_name = "w3af.core.controllers.daemons.webserver"

        with self.assertLogs(logger_name, level="ERROR") as logs:
            thread.start()
            connection = http.client.HTTPConnection(IP, server.get_port())
            connection.request("GET", "/")
            with self.assertRaises(ConnectionResetError):
                connection.getresponse()
            connection.close()
            thread.join(SHUTDOWN_TIMEOUT)

        self.assertIn("Error processing request", logs.output[0])
        self.assertTrue(server.is_down())
