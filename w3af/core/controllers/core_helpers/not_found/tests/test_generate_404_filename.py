# -*- coding: UTF-8 -*-
"""
test_generate_404_filename.py

Copyright 2018 Andres Riancho

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

import unittest

from w3af.core.controllers.core_helpers.not_found.generate_404 import (
    generate_404_filename,
    get_url_for_404_request,
    send_404,
)
from w3af.core.controllers.tests.local_http_server import (
    LocalHTTPServer,
    Reply,
    closed_local_port,
)
from w3af.core.data.dc.headers import Headers
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.url.extended_urllib import ExtendedUrllib
from w3af.core.data.url.http_response import HTTPResponse
from w3af.core.exceptions import FourOhFourDetectionException


class TestGenerate404Filename(unittest.TestCase):
    def test_404_generation(self):

        tests = [
            ("ab-23", "ab-53"),
            ("abc-12", "abc-21"),
            ("ab-23.html", "ab-53.html"),
            ("a1a2", "a1d2"),
            ("a1a2.html", "a1d2.html"),
            ("hello.html", "heolo.html"),
            ("r57_Mohajer22.php", "r57_oMahejr22.php"),
            # short filename: a deterministic prefix is prepended
            ("Z", "iK2ZZ"),
        ]

        for fname, modfname in tests:
            self.assertEqual(generate_404_filename(fname), modfname)

    def test_404_generation_twice(self):
        self.assertEqual(generate_404_filename("Entries"), "Entreis")
        self.assertEqual(generate_404_filename("Entries", seed=2), "Enrteis")
        self.assertEqual(generate_404_filename("Entries", seed=3), "nErteis")

    def test_404_generation_without_filename(self):
        self.assertEqual(generate_404_filename(""), "iK2ZW")

    def test_404_generation_without_name(self):
        self.assertEqual(generate_404_filename(".env"), "iK2ZW.env")

    def test_404_generation_shuffles_when_nothing_can_be_flipped(self):
        self.assertEqual(generate_404_filename("-_-"), "_--")
        self.assertEqual(generate_404_filename("-_-.php"), "_--.php")


class TestGetURLFor404Request(unittest.TestCase):
    def get_url(self, url):
        url = URL(url)
        response = HTTPResponse(200, "", Headers(), url, url)
        return get_url_for_404_request(response).url_string

    def test_root_path(self):
        self.assertEqual(self.get_url("http://w3af.org/"), "http://w3af.org/iK2ZW")

    def test_directory(self):
        self.assertEqual(
            self.get_url("http://w3af.org/dir/"), "http://w3af.org/iK2ZWeqh/"
        )

    def test_filename(self):
        self.assertEqual(
            self.get_url("http://w3af.org/dir/x.php"), "http://w3af.org/dir/iK2Zx.php"
        )


class TestSend404(unittest.TestCase):
    def setUp(self):
        self.uri_opener = ExtendedUrllib()
        self.addCleanup(self.uri_opener.end)

    def test_raises_detection_exception_when_the_request_fails(self):
        url_404 = URL(f"http://127.0.0.1:{closed_local_port()}/iK2ZW")

        with self.assertRaises(FourOhFourDetectionException) as context:
            send_404(self.uri_opener, url_404, debugging_id="did404")

        self.assertIn("Exception found while detecting 404", str(context.exception))
        self.assertIn("did404", str(context.exception))

    def test_returns_the_response(self):
        def respond(method, path):
            return Reply(status=404, body="Not here")

        with LocalHTTPServer(respond) as server:
            response = send_404(self.uri_opener, URL(server.url("/iK2ZW")))

        self.assertEqual(response.get_code(), 404)
        self.assertEqual(response.get_body(), "Not here")
