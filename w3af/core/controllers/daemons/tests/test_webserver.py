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

import contextlib
import os
import tempfile
import unittest
import urllib.error
import urllib.parse
import urllib.request

from w3af.core.controllers.daemons.webserver import (
    start_webserver,
    start_webserver_any_free_port,
)
from w3af.core.data.constants.ports import REMOTEFILEINCLUDE


class TestWebserver(unittest.TestCase):

    IP = "127.0.0.1"
    PORT = REMOTEFILEINCLUDE
    TESTSTRING = "abc<>def"

    def setUp(self):
        self.tempdir = tempfile.gettempdir()

        for port in range(self.PORT, self.PORT + 15):
            with contextlib.suppress(OSError):
                self.server = start_webserver(self.IP, port, self.tempdir)
                self.PORT = port
                break

    def test_GET_404(self):
        # Raises a 404
        self.assertRaises(
            urllib.error.HTTPError,
            urllib.request.urlopen,
            f"http://{self.IP}:{self.PORT}",
        )

    def _create_file(self):
        # Create a file and request it
        with open(os.path.join(self.tempdir, "foofile.txt"), "w") as test_fh:
            test_fh.write(self.TESTSTRING)

    def test_is_down(self):
        # pylint: disable=E1103
        self.assertFalse(self.server.is_down())
        # pylint: enable=E1103

    def test_GET_exists(self):
        self._create_file()

        url = f"http://{self.IP}:{self.PORT}/foofile.txt"
        response_body = urllib.request.urlopen(url).read().decode("utf-8")

        self.assertEqual(response_body, self.TESTSTRING)

    def test_any_free_port(self):
        self._create_file()
        _, port = start_webserver_any_free_port(self.IP, self.tempdir)

        url = f"http://{self.IP}:{port}/foofile.txt"
        response_body = urllib.request.urlopen(url).read().decode("utf-8")

        self.assertEqual(response_body, self.TESTSTRING)
