"""
test_blacklist.py

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

import re
import unittest
import urllib.request

import w3af.core.data.kb.config as cf
from w3af.core.data.constants.response_codes import NO_CONTENT
from w3af.core.data.misc.number_generator import consecutive_number_generator
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.url import opener_settings
from w3af.core.data.url.handlers.blacklist import BlacklistHandler
from w3af.core.data.url.http_request import HTTPRequest
from w3af.core.data.url.tests.helpers.route_server import Response, RouteServer


class TestBlacklistHandler(unittest.TestCase):

    SCANNER_PATH = "/scanner/"
    BLOCK_PATH = "/block/"
    PASS_PATH = "/pass/"
    BODY = "Hello world"

    def setUp(self):
        consecutive_number_generator.reset()
        cf.cf.save("blacklist_http_request", [])
        cf.cf.save("ignore_regex", None)

        self.server = RouteServer()
        for path in (self.SCANNER_PATH, self.BLOCK_PATH, self.PASS_PATH):
            self.server.add("GET", path, Response(body=self.BODY))
        self.server.start()

    def tearDown(self):
        self.server.stop()
        cf.cf.save("blacklist_http_request", [])
        cf.cf.save("ignore_regex", None)

    def build_custom_opener(self):
        settings = opener_settings.OpenerSettings()
        settings.build_openers()
        return settings.get_custom_opener()

    def test_blacklist_handler_block(self):
        blocked_url = URL(self.server.url(self.SCANNER_PATH))
        cf.cf.save("blacklist_http_request", [blocked_url])

        opener = urllib.request.build_opener(BlacklistHandler)

        request = urllib.request.Request(blocked_url.url_string)
        request.url_object = blocked_url
        response = opener.open(request)

        self.assertEqual(response.code, NO_CONTENT)
        self.assertEqual(self.server.requests, [])

    def test_blacklist_handler_pass(self):
        url = self.server.url(self.SCANNER_PATH)
        opener = urllib.request.build_opener(BlacklistHandler)

        request = urllib.request.Request(url)
        request.url_object = URL(url)
        response = opener.open(request)

        self.assertEqual(response.code, 200)
        self.assertEqual(self.server.last_request.method, "GET")

    def test_handler_order_block(self):
        blocked_url = URL(self.server.url(self.SCANNER_PATH))
        cf.cf.save("blacklist_http_request", [blocked_url])

        # Get an instance of the extended urllib and verify that the blacklist
        # handler still works, even when mixed with all the other handlers.
        opener = self.build_custom_opener()

        response = opener.open(HTTPRequest(blocked_url))

        self.assertEqual(response.code, NO_CONTENT)
        self.assertEqual(response.id, 1)
        self.assertEqual(self.server.requests, [])

    def assert_safe_sent_and_blocked_not_sent(self, opener):
        blocked_url = URL(self.server.url(self.BLOCK_PATH))
        safe_url = URL(self.server.url(self.PASS_PATH))

        response = opener.open(HTTPRequest(safe_url))

        self.assertEqual(response.code, 200)
        self.assertEqual(response.id, 1)
        self.assertEqual(self.server.last_request.method, "GET")
        self.assertEqual(len(self.server.requests), 1)

        response = opener.open(HTTPRequest(blocked_url))

        self.assertEqual(response.code, NO_CONTENT)
        self.assertEqual(response.id, 2)
        self.assertEqual(len(self.server.requests), 1)

    def test_handler_order_pass(self):
        cf.cf.save("blacklist_http_request", [URL(self.server.url(self.BLOCK_PATH))])

        self.assert_safe_sent_and_blocked_not_sent(self.build_custom_opener())

    def test_handler_order_pass_with_ignore_regex(self):
        cf.cf.save("ignore_regex", re.compile(".*block.*"))

        self.assert_safe_sent_and_blocked_not_sent(self.build_custom_opener())

    def test_handler_order_pass_with_both_methods(self):
        cf.cf.save("blacklist_http_request", [URL(self.server.url(self.BLOCK_PATH))])
        cf.cf.save("ignore_regex", re.compile(".*blo.*"))

        self.assert_safe_sent_and_blocked_not_sent(self.build_custom_opener())
