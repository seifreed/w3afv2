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

import hashlib
import os
import re
import secrets
import unittest

import w3af.core.controllers.output_manager as om
import w3af.core.data.kb.config as cf
from w3af.core.controllers.core_helpers.fingerprint_404 import (
    Fingerprint404,
    fingerprint_404_singleton,
    is_404,
)
from w3af.core.controllers.misc.fuzzy_string_cmp import MAX_FUZZY_LENGTH
from w3af.core.controllers.tests.local_http_server import LocalHTTPServer, Reply
from w3af.core.data.dc.headers import Headers
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.url.extended_urllib import ExtendedUrllib
from w3af.core.data.url.helpers import new_no_content_resp
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
        parts = [re.__doc__, secrets.__doc__, unittest.__doc__]
        parts = parts * 30

        parts.extend(unique_parts)

        parts = sorted(
            enumerate(parts),
            key=lambda item: hashlib.sha256(f"1:{item[0]}:{item[1]}".encode()).digest(),
        )
        parts = [part for _, part in parts]

        body = "\n".join(parts)

        return body

    def target_url(self, path):
        return URL(self.server.url(path))

    def setUp(self):
        self.server = LocalHTTPServer(self.respond).start()

        self.urllib = ExtendedUrllib()

        self.fingerprint_404 = Fingerprint404(om.out)
        self.fingerprint_404.set_url_opener(self.urllib)

    def tearDown(self):
        self.urllib.end()
        self.server.close()


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
            f"{secrets.randbelow(99999) + 1}",
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
    """
    Large 404 pages which embed the ID of the application server that
    generated them. The ID is a token that changes between responses, which
    the diff-based comparison for large responses ignores.
    """

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
            f'<meta name="application-server" content="{app_server_num}">',
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

    def assert_ignored_part_is_reported_as_404(self, path):
        """
        The URL is valid, but is_404() reports it as a 404 because it does not
        support the sites described in IGNORED_PATH_PARTS_DOC
        """
        query_url = self.target_url(path)
        headers = Headers([("Content-Type", "text/html")])
        success_200 = HTTPResponse(
            200, self.ALL_SAME_BODY, headers, query_url, query_url
        )

        self.assertTrue(self.fingerprint_404.is_404(success_200))


class Test404HandleIgnoredFilename(GenericIgnoredPartTest):

    def test_handle_ignored_filename(self):
        self.assert_ignored_part_is_reported_as_404("/path1/path2/xyz123")


class Test404HandleIgnoredPath(GenericIgnoredPartTest):

    def test_handle_ignored_path(self):
        self.assert_ignored_part_is_reported_as_404("/path1/path2/path3/")


class Test404HandleIgnoredPathAndFilename(GenericIgnoredPartTest):

    def test_handle_ignored_path(self):
        self.assert_ignored_part_is_reported_as_404("/path1/path2/path3/xyz123")


class Test404HandleIgnoredPathDeep(GenericIgnoredPartTest):

    def test_handle_ignored_path(self):
        self.assert_ignored_part_is_reported_as_404("/path1/path2/path3/path4/path5/")


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


class Test404UserConfiguration(Generic404Test):

    def respond(self, method, path):
        return Reply(status=404, body="Not found")

    def configure(self, name, value, default):
        cf.cf.save(name, value)
        self.addCleanup(cf.cf.save, name, default)

    def build_response(self, path, code=200, body="Some content"):
        url = self.target_url(path)
        headers = Headers([("Content-Type", "text/html")])
        return HTTPResponse(code, body, headers, url, url)

    def test_never_404(self):
        response = self.build_response("/never/index.html", code=404)
        self.configure("never_404", [response.get_url().get_domain_path()], [])

        self.assertFalse(self.fingerprint_404.is_404(response))

    def test_always_404(self):
        response = self.build_response("/always/index.html")
        self.configure("always_404", [response.get_url().get_domain_path()], [])

        self.assertTrue(self.fingerprint_404.is_404(response))

    def test_string_match_404(self):
        self.configure("string_match_404", "Custom missing page marker", "")
        response = self.build_response(
            "/match.html", body="<p>Custom missing page marker</p>"
        )

        self.assertTrue(self.fingerprint_404.is_404(response))

    def test_404_code(self):
        response = self.build_response("/missing.html", code=404)

        self.assertTrue(self.fingerprint_404.is_404(response))

    def test_no_content_response_generated_by_w3af(self):
        response = new_no_content_resp(self.target_url("/no-content.html"))

        self.assertTrue(self.fingerprint_404.is_404(response))

    def test_200_is_not_404_when_the_site_uses_404_codes(self):
        response = self.build_response("/exists.html")

        self.assertFalse(self.fingerprint_404.is_404(response))


class Test404ContentTypeMismatch(Generic404Test):

    def respond(self, method, path):
        return Reply(body="The page you requested was not found")

    def test_image_is_not_404(self):
        url = self.target_url("/images/logo.png")
        headers = Headers([("Content-Type", "image/png")])
        image = HTTPResponse(
            200, "The page you requested was not found", headers, url, url
        )

        self.assertFalse(self.fingerprint_404.is_404(image))


class Test404FuzzyEqualShortResponses(Generic404Test):

    COMMON_LINES = tuple(f"Common navigation line number {i}" for i in range(20))

    def respond(self, method, path):
        return Reply(body=self.get_short_body("The page was not found"))

    def get_short_body(self, unique_line):
        return "\n".join([*self.COMMON_LINES, unique_line])

    def test_fuzzy_equal_short_response_is_404(self):
        url = self.target_url("/short/page.html")
        headers = Headers([("Content-Type", "text/html")])
        body = self.get_short_body("The requested page does not exist")
        response = HTTPResponse(200, body, headers, url, url)

        self.assertTrue(self.fingerprint_404.is_404(response))

    def test_known_404_is_read_from_the_404_db(self):
        headers = Headers([("Content-Type", "text/html")])

        first_url = self.target_url("/short/first.html")
        first_body = self.get_short_body("The requested page does not exist")
        first = HTTPResponse(200, first_body, headers, first_url, first_url)

        second_url = self.target_url("/short/second.html")
        second_body = self.get_short_body("Sorry, there is nothing here")
        second = HTTPResponse(200, second_body, headers, second_url, second_url)

        self.assertTrue(self.fingerprint_404.is_404(first))
        self.assertTrue(self.fingerprint_404.is_404(second))

        self.assertEqual(len(self.server.requested_paths), 1)


class Test404LargeResponsesReuseDiff(Generic404Test):
    """
    The bodies have no HTML tags, so the 404 cache can not match them by
    their XML bones and each one is compared with the known 404.
    """

    SHARED_LINES = tuple(
        f"Shared line {i} of every page in this site" for i in range(200)
    )
    NOT_FOUND_LINES = ("The request failed", "Come back later")

    def respond(self, method, path):
        return Reply(body=self.get_large_body(self.NOT_FOUND_LINES))

    def get_large_body(self, unique_lines):
        return "\n".join([*self.SHARED_LINES, *unique_lines])

    def build_response(self, path, unique_lines):
        url = self.target_url(path)
        headers = Headers([("Content-Type", "text/html")])
        body = self.get_large_body(unique_lines)
        return HTTPResponse(200, body, headers, url, url)

    def test_diff_with_second_404_is_calculated_once(self):
        not_found = self.build_response("/large/first/", self.NOT_FOUND_LINES)
        welcome = self.build_response("/large/second/", ["Welcome to our site"])
        contact = self.build_response("/large/third/", ["Contact us by email"])

        self.assertTrue(self.fingerprint_404.is_404(not_found))
        self.assertFalse(self.fingerprint_404.is_404(welcome))
        self.assertFalse(self.fingerprint_404.is_404(contact))

        self.assertEqual(len(self.server.requested_paths), 2)


class TestFingerprint404Singleton(unittest.TestCase):

    def tearDown(self):
        fingerprint_404_singleton(om.out, cleanup=True)

    def test_returns_the_same_instance(self):
        self.assertIs(
            fingerprint_404_singleton(om.out), fingerprint_404_singleton(om.out)
        )

    def test_cleanup_creates_a_new_instance(self):
        instance = fingerprint_404_singleton(om.out)

        self.assertIsNot(fingerprint_404_singleton(om.out, cleanup=True), instance)

    def test_is_404_uses_the_singleton(self):
        url = URL("http://w3af.org/missing.html")
        response = HTTPResponse(404, "Not found", Headers(), url, url)

        self.assertTrue(is_404(response, om.out))
