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

    BODY = "Hello world"

    def setUp(self):
        consecutive_number_generator.reset()
        cf.cf.save("blacklist_http_request", [])
        cf.cf.save("ignore_regex", None)

        routes = {
            path: Response(body=self.BODY)
            for path in ("/scanner/", "/block/", "/pass/")
        }
        self.server = RouteServer(routes).start()
        self.addCleanup(self.server.stop)

        self.scanner_url = URL(self.server.url("/scanner/"))
        self.blocked_url = URL(self.server.url("/block/"))
        self.safe_url = URL(self.server.url("/pass/"))

    def tearDown(self):
        cf.cf.save("blacklist_http_request", [])
        cf.cf.save("ignore_regex", None)

    def sent_paths(self):
        return [request.path for request in self.server.requests]

    def w3af_opener(self):
        # Get an instance of the extended urllib and verify that the blacklist
        # handler still works, even when mixed with all the other handlers.
        settings = opener_settings.OpenerSettings(configuration=cf.cf)
        settings.build_openers()
        return settings.get_custom_opener()

    def test_blacklist_handler_block(self):
        cf.cf.save("blacklist_http_request", [self.scanner_url])

        opener = urllib.request.build_opener(BlacklistHandler(cf.cf))

        request = urllib.request.Request(self.scanner_url.url_string)
        request.url_object = self.scanner_url
        response = opener.open(request)

        self.assertEqual(response.code, NO_CONTENT)
        self.assertEqual(response.msg, "No content")
        self.assertEqual(response.read(), "")
        self.assertEqual(self.sent_paths(), [])

    def test_blacklist_handler_pass(self):
        opener = urllib.request.build_opener(BlacklistHandler(cf.cf))

        request = urllib.request.Request(self.scanner_url.url_string)
        request.url_object = self.scanner_url
        response = opener.open(request)

        self.assertEqual(response.code, 200)
        self.assertEqual(self.server.requests[0].method, "GET")

    def test_handler_order_block(self):
        cf.cf.save("blacklist_http_request", [self.scanner_url])

        response = self.w3af_opener().open(HTTPRequest(self.scanner_url))

        self.assertEqual(response.code, NO_CONTENT)
        self.assertEqual(response.id, 1)
        self.assertEqual(self.sent_paths(), [])

    def assert_only_safe_url_is_sent(self):
        opener = self.w3af_opener()

        response = opener.open(HTTPRequest(self.safe_url))
        self.assertEqual(response.code, 200)
        self.assertEqual(response.id, 1)

        response = opener.open(HTTPRequest(self.blocked_url))
        self.assertEqual(response.code, NO_CONTENT)
        self.assertEqual(response.id, 2)

        self.assertEqual(self.sent_paths(), ["/pass/"])

    def test_handler_order_pass(self):
        cf.cf.save("blacklist_http_request", [self.blocked_url])
        self.assert_only_safe_url_is_sent()

    def test_handler_order_pass_with_ignore_regex(self):
        cf.cf.save("ignore_regex", re.compile(".*block.*"))
        self.assert_only_safe_url_is_sent()

    def test_handler_order_pass_with_both_methods(self):
        cf.cf.save("blacklist_http_request", [self.blocked_url])
        cf.cf.save("ignore_regex", re.compile(".*blo.*"))
        self.assert_only_safe_url_is_sent()
