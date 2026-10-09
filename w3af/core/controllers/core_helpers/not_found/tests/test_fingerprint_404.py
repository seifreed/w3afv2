# -*- coding: UTF-8 -*-
"""
test_fingerprint_404.py

Copyright 2014 Andres Riancho

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

import os
import random
import re
import unittest

from w3af.core.controllers.core_helpers.fingerprint_404 import Fingerprint404
from w3af.core.controllers.misc.fuzzy_string_cmp import MAX_FUZZY_LENGTH
from w3af.core.controllers.tests.local_http_server import LocalHTTPServer, Reply
from w3af.core.data.db.dbms import clear_default_temp_db_instance
from w3af.core.data.dc.headers import Headers
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.url.extended_urllib import ExtendedUrllib
from w3af.core.data.url.http_response import HTTPResponse


class Generic404Test(unittest.TestCase):
    """
    Every test runs against a real HTTP server listening on 127.0.0.1, which
    answers all requests (including the ones sent by Fingerprint404 to learn
    how the site's 404 pages look like) using respond().
    """

    def respond(self, method, path):
        raise NotImplementedError

    def get_body(self, unique_parts):
        # Do not increase this 30 too much, it will exceed the xurllib max
        # HTTP response body length (max_file_size)
        parts = [re.__doc__, random.__doc__, unittest.__doc__]
        parts = parts * 30

        parts.extend(unique_parts)

        rnd = random.Random()
        rnd.seed(1)
        rnd.shuffle(parts)

        body = "\n".join(parts)

        return body

    def target_url(self, path):
        return URL(self.server.url(path))

    def setUp(self):
        self.server = LocalHTTPServer(self.respond).start()

        self.urllib = ExtendedUrllib()

        self.fingerprint_404 = Fingerprint404()
        self.fingerprint_404.set_url_opener(self.urllib)

    def tearDown(self):
        self.urllib.end()
        self.server.close()
        clear_default_temp_db_instance()


class Test404Detection(Generic404Test):

    def respond(self, method, path):
        return Reply(status=404, body="404 found")

    def test_issue_3234(self):
        #
        # is_404 can not handle URLs with : in path #3234
        # https://github.com/andresriancho/w3af/issues/3234
        #
        url = self.target_url("/d:a")
        resp = HTTPResponse(200, "body", Headers(), url, url)

        self.assertFalse(self.fingerprint_404.is_404(resp))


class Test404FalseNegative(Generic404Test):

    SERVER_ERROR = (
        "500 error that does NOT\n"
        "look like one\n"
        "because we want to reproduce the bug\n"
    )

    NOT_FOUND = (
        "This is a 404\n"
        "but it does NOT look like one\n"
        "because we want to reproduce the bug\n"
    )

    def respond(self, method, path):
        if path.startswith("/foo/"):
            return Reply(status=500, body=self.SERVER_ERROR)

        return Reply(status=404, body=self.NOT_FOUND)

    def test_false_negative_with_500(self):
        foo_url = self.target_url("/foo/phpinfo.php")
        headers = Headers([("Content-Type", "text/html")])
        server_error_resp = HTTPResponse(
            500, self.SERVER_ERROR, headers, foo_url, foo_url
        )

        self.assertTrue(self.fingerprint_404.is_404(server_error_resp))


class Test404FalsePositiveLargeResponsesRandomShort(Generic404Test):

    def respond(self, method, path):
        return Reply(body=self.get_random_unique_parts_body())

    def get_random_unique_parts_body(self):
        unique_parts = [
            "The request failed",
            "Come back later",
            f"{random.randint(1, 99999)}",
        ]
        return self.get_body(unique_parts)

    def test_page_found_with_large_response_random(self):
        success_url = self.target_url("/fid2/")

        unique_parts = [
            "Welcome to our site",
            "Content is being loaded using async JS",
            "Please wait...",
        ]
        body = self.get_body(unique_parts)
        headers = Headers([("Content-Type", "text/html")])
        success_200 = HTTPResponse(200, body, headers, success_url, success_url)
        self.assertFalse(self.fingerprint_404.is_404(success_200))

    def test_page_marked_as_404_with_large_response_random(self):
        not_found_url = self.target_url("/dnliw9a/")

        body = self.get_random_unique_parts_body()

        headers = Headers([("Content-Type", "text/html")])
        not_found = HTTPResponse(200, body, headers, not_found_url, not_found_url)
        self.assertTrue(self.fingerprint_404.is_404(not_found))


class Test404With1ByteRandomShort(Generic404Test):

    def setUp(self):
        self.application_server_ids = [1, 2, 2]
        self.application_server_idx = 0
        super().setUp()

    def respond(self, method, path):
        return Reply(body=self.get_short_body())

    def get_short_body(self):
        app_server_num = self.application_server_ids[self.application_server_idx]
        self.application_server_idx += 1

        parts = [
            "The request failed",
            "Come back later",
            f"Generated by application server ID {app_server_num}",
        ]

        return "\n".join(parts)

    def test_1byte_short_not_404(self):
        success_url = self.target_url("/search/feed/CVS/Entries")

        body = self.get_short_body()
        headers = Headers([("Content-Type", "text/html")])
        success_200 = HTTPResponse(200, body, headers, success_url, success_url)
        self.assertFalse(self.fingerprint_404.is_404(success_200))


class Test404With1ByteRandomLarge(Generic404Test):

    def setUp(self):
        self.application_server_ids = [1, 2, 2]
        self.application_server_idx = 0
        super().setUp()

    def respond(self, method, path):
        return Reply(body=self.get_short_body())

    def get_short_body(self):
        app_server_num = self.application_server_ids[self.application_server_idx]
        self.application_server_idx += 1

        parts = [
            "The request failed",
            "Come back later",
            f"Generated by application server ID {app_server_num}",
        ]

        count = 8
        padding = "A" * int(MAX_FUZZY_LENGTH / count)
        padding_list = [padding] * count

        parts.extend(padding_list)

        return "\n".join(parts)

    def test_1byte_large_is_404(self):
        not_found_url = self.target_url("/search/feed/SVN/Entries")

        body = self.get_short_body()
        headers = Headers([("Content-Type", "text/html")])
        not_found = HTTPResponse(200, body, headers, not_found_url, not_found_url)
        self.assertTrue(self.fingerprint_404.is_404(not_found))

    def test_1byte_large_is_200(self):
        success_url = self.target_url("/search/feed/.bzr/.ignore")

        body = "I exist, that is a fact"
        headers = Headers([("Content-Type", "text/html")])
        success_200 = HTTPResponse(200, body, headers, success_url, success_url)
        self.assertFalse(self.fingerprint_404.is_404(success_200))


class Test404FalsePositiveLargeResponsesEqual404s(Generic404Test):

    def respond(self, method, path):
        return Reply(body=self.get_body_with_unique_params())

    def get_body_with_unique_params(self):
        unique_parts = ["The request failed", "Come back later"]
        return self.get_body(unique_parts)

    def test_page_not_found_with_large_response(self):
        success_url = self.target_url("/fiaasxd322/")

        unique_parts = [
            "Welcome to our site",
            "Content is being loaded using async JS",
            "Please wait...",
        ]
        body = self.get_body(unique_parts)
        headers = Headers([("Content-Type", "text/html")])
        success_200 = HTTPResponse(200, body, headers, success_url, success_url)
        self.assertFalse(self.fingerprint_404.is_404(success_200))

    def test_page_marked_as_404_with_large_response(self):
        not_found_url = self.target_url("/nfklu/")

        body = self.get_body_with_unique_params()

        headers = Headers([("Content-Type", "text/html")])
        not_found = HTTPResponse(200, body, headers, not_found_url, not_found_url)
        self.assertTrue(self.fingerprint_404.is_404(not_found))


class Test404FalsePositiveLargeResponsesWithCSRFToken(Generic404Test):

    def generate_csrf_token(self):
        return os.urandom(64).hex()

    def respond(self, method, path):
        return Reply(body=self.get_body([self.generate_csrf_token()]))

    def test_is_404_with_csrf_token(self):
        not_found_url = self.target_url("/xfi/")

        unique_parts = [self.generate_csrf_token()]
        body = self.get_body(unique_parts)
        headers = Headers([("Content-Type", "text/html")])
        not_found_404 = HTTPResponse(200, body, headers, not_found_url, not_found_url)

        self.assertTrue(self.fingerprint_404.is_404(not_found_404))

    def test_exists_with_csrf_token_in_404_page(self):
        success_url = self.target_url("/fenix/")

        body = "I do exist, completely different from the 404 page"
        headers = Headers([("Content-Type", "text/html")])
        success_response = HTTPResponse(200, body, headers, success_url, success_url)

        self.assertFalse(self.fingerprint_404.is_404(success_response))


class Test404FalsePositiveLargeResponsesWithCSRFTokenPartiallyEqual(Generic404Test):

    def generate_csrf_token(self):
        part_1 = os.urandom(32).hex()
        part_2 = os.urandom(32).hex()

        shared = "aabbccdd112233"

        return part_1 + shared + part_2

    def respond(self, method, path):
        return Reply(body=self.get_body([self.generate_csrf_token()]))

    def test_false_positive(self):
        success_url = self.target_url("/321x/")

        unique_parts = [self.generate_csrf_token()]
        body = self.get_body(unique_parts)
        headers = Headers([("Content-Type", "text/html")])
        also_404 = HTTPResponse(200, body, headers, success_url, success_url)

        self.assertTrue(self.fingerprint_404.is_404(also_404))


class GenericIgnoredPartTest(Generic404Test):
    ALL_SAME_BODY = (
        "All filenames in this path return the same HTTP"
        " response body, but that does NOT mean that the"
        " URL is a 404.\n"
        "\n"
        "The URL is completely valid, but the last part,"
        " the filename, does not influence the HTTP response"
        " body in any way.\n"
        "\n"
        "Also, removing the filename will yield a completely"
        " different result, because the url-rewrite rule does"
        " NOT match for that URL and the page returns something"
        " completely different."
        "\n"
        "Heavy URL-rewrite based sites do this.\n"
        "\n"
        ":-S"
    )

    IGNORED_PATH_PARTS_DOC = (
        "The is_404() function never supported and does"
        " not currently support sites which do heavy use"
        " of URL-rewriting (see ALL_SAME_BODY), and more"
        " specifically the sites that ignore the filename"
        " or last part of the path while deciding which"
        " HTTP response to generate."
        ""
        "The good news is that most likely the get_directories()"
        " in web_spider is helping in these cases. For example,"
        " when http://w3af.org/foo/ignored is found, then the"
        " get_directories() call will test TWO URLs, one with"
        " the filename, and one without. The one without the"
        " ignored filename will most likely not be marked as a"
        " 404 and make it to the audit process."
        ""
        "Note written: 11-Dec-2018"
    )

    def respond(self, method, path):
        if "/path1/path2/" in path:
            body = self.ALL_SAME_BODY
        elif "/path1/" in path:
            body = "The second path controls the HTTP response body"
        else:
            raise RuntimeError("Should never reach this.")

        return Reply(body=body)

    def assert_ignored_part_is_not_404(self, path):
        # This is the URL we found during crawling and want to know if is_404()
        query_url = self.target_url(path)
        headers = Headers([("Content-Type", "text/html")])
        success_200 = HTTPResponse(
            200, self.ALL_SAME_BODY, headers, query_url, query_url
        )

        self.assertFalse(self.fingerprint_404.is_404(success_200))


class Test404HandleIgnoredFilename(GenericIgnoredPartTest):

    @unittest.skip("See: IGNORED_PATH_PARTS_DOC")
    def test_handle_ignored_filename(self):
        self.assert_ignored_part_is_not_404("/path1/path2/xyz123")


class Test404HandleIgnoredPath(GenericIgnoredPartTest):

    @unittest.skip("See: IGNORED_PATH_PARTS_DOC")
    def test_handle_ignored_path(self):
        self.assert_ignored_part_is_not_404("/path1/path2/path3/")


class Test404HandleIgnoredPathAndFilename(GenericIgnoredPartTest):

    @unittest.skip("See: IGNORED_PATH_PARTS_DOC")
    def test_handle_ignored_path(self):
        self.assert_ignored_part_is_not_404("/path1/path2/path3/xyz123")


class Test404HandleIgnoredPathDeep(GenericIgnoredPartTest):

    @unittest.skip("See: IGNORED_PATH_PARTS_DOC")
    def test_handle_ignored_path(self):
        self.assert_ignored_part_is_not_404("/path1/path2/path3/path4/path5/")


class Test404HandleAllIs404(GenericIgnoredPartTest):

    def respond(self, method, path):
        return Reply(body=self.ALL_SAME_BODY)

    def test_handle_really_a_404(self):
        # This is the URL we found during crawling and want to know if is_404()
        query_url = self.target_url("/path1/path2/")
        headers = Headers([("Content-Type", "text/html")])
        success_200 = HTTPResponse(
            200, self.ALL_SAME_BODY, headers, query_url, query_url
        )

        self.assertTrue(self.fingerprint_404.is_404(success_200))
