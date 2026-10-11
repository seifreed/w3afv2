"""
test_errors.py

Copyright 2013 Andres Riancho

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
import urllib.error
from typing import Any, cast

from w3af.core.data.constants.response_codes import NOT_FOUND
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.url import opener_settings
from w3af.core.data.url.director import CustomOpenerDirector, build_opener
from w3af.core.data.url.handlers.errors import ErrorHandler
from w3af.core.data.url.handlers.keepalive import HTTPHandler
from w3af.core.data.url.http_request import HTTPRequest
from w3af.core.data.url.tests.helpers.route_server import RouteServer


class TestErrorHandler(unittest.TestCase):
    def setUp(self):
        self.server = RouteServer().start()
        self.addCleanup(self.server.stop)
        self.fail_url = URL(self.server.url("/abc/def/do-not-exist.foo"))

    def test_w3af_opener_returns_error_responses(self):
        """
        Verify that the error handlers work as expected, in other words, do NOT
        crash on response codes not in range 200-300.
        """
        settings = opener_settings.OpenerSettings()
        settings.build_openers()
        opener = settings.get_custom_opener()

        response = opener.open(HTTPRequest(self.fail_url))

        self.assertEqual(response.code, NOT_FOUND)
        self.assertEqual(response.id, 1)

    def test_error_handler_id(self):
        opener = build_opener(CustomOpenerDirector, [HTTPHandler(), ErrorHandler])
        request = HTTPRequest(self.fail_url)
        request_with_id = cast(Any, request)
        request_with_id.id = 42

        with self.assertRaises(urllib.error.HTTPError) as error:
            opener.open(request)

        self.assertEqual(error.exception.code, NOT_FOUND)
        self.assertEqual(error.exception.id, 42)
        error.exception.close()
