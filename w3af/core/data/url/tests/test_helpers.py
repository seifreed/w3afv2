"""
test_helpers.py

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
import ssl
import unittest
import urllib.error
from errno import ECONNREFUSED, ECONNRESET, EPERM

import OpenSSL

from w3af.core.data.constants.response_codes import NO_CONTENT
from w3af.core.data.dc.headers import Headers
from w3af.core.data.fuzzer.mutants.tests.test_mutant import FakeMutant
from w3af.core.data.misc.number_generator import NumberGenerator
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.request.fuzzable_request import FuzzableRequest
from w3af.core.data.url.exceptions import HTTPRequestException
from w3af.core.data.url.handlers.keepalive import URLTimeoutError
from w3af.core.data.url.helpers import (
    EUNEXPECTEDEOF,
    NO_CONTENT_MSG,
    get_clean_body,
    get_clean_body_impl,
    get_exception_reason,
    get_socket_exception_reason,
    is_no_content_response,
    new_no_content_resp,
)
from w3af.core.data.url.http_response import HTTPResponse

URI = URL("http://w3af.org/")


class TestNoContentResponse(unittest.TestCase):

    def test_new_no_content_resp(self):
        response = new_no_content_resp(URI)

        self.assertEqual(response.get_code(), NO_CONTENT)
        self.assertEqual(response.get_msg(), NO_CONTENT_MSG)
        self.assertIsNone(response.id)
        self.assertTrue(is_no_content_response(response))

    def test_new_no_content_resp_with_id(self):
        id_generator = NumberGenerator()
        first = new_no_content_resp(URI, add_id=True, id_generator=id_generator)
        second = new_no_content_resp(URI, add_id=True, id_generator=id_generator)

        self.assertEqual(second.id, first.id + 1)

    def test_is_no_content_response_false(self):
        ok = HTTPResponse(200, "", Headers(), URI, URI, msg=NO_CONTENT_MSG)
        other_msg = HTTPResponse(NO_CONTENT, "", Headers(), URI, URI, msg="Empty")
        with_headers = HTTPResponse(
            NO_CONTENT, "", Headers([("A", "b")]), URI, URI, msg=NO_CONTENT_MSG
        )

        for response in (ok, other_msg, with_headers):
            self.assertFalse(is_no_content_response(response))


class TestGetCleanBody(unittest.TestCase):

    def test_non_text_body_is_not_cleaned(self):
        mutant = FakeMutant(FuzzableRequest(URL("http://w3af.org/?id=1")))
        mutant.set_token(("id", 0))
        mutant.set_token_value("abc")

        headers = Headers([("Content-Type", "image/png")])
        response = HTTPResponse(200, b"abc", headers, URI, URI)

        self.assertEqual(get_clean_body(mutant, response), b"abc")

    def test_payload_longer_than_body(self):
        self.assertEqual(get_clean_body_impl("abc", ["abcdef"]), "abc")


class TestExceptionReason(unittest.TestCase):

    def test_socket_exception_reason(self):
        refused = OSError(ECONNREFUSED, "Connection refused")

        self.assertIsNone(get_socket_exception_reason(ValueError("x")))
        self.assertEqual(get_socket_exception_reason(refused), str(refused))
        self.assertIsNone(get_socket_exception_reason(OSError(EPERM, "Denied")))

    def test_timeout(self):
        self.assertEqual(get_exception_reason(URLTimeoutError()), "HTTP timeout error")

    def test_url_error_with_socket_reason(self):
        refused = ConnectionRefusedError(ECONNREFUSED, "Connection refused")
        error = urllib.error.URLError(refused)

        self.assertEqual(get_exception_reason(error), str(refused))

    def test_url_error_with_unknown_socket_reason(self):
        error = urllib.error.URLError(OSError(EPERM, "Denied"))
        self.assertIsNone(get_exception_reason(error))

    def test_bad_status_line(self):
        self.assertEqual(
            get_exception_reason(http.client.BadStatusLine("HTTP/9 OK")),
            "Bad HTTP response status line: HTTP/9 OK",
        )
        self.assertEqual(
            get_exception_reason(http.client.RemoteDisconnected("closed")),
            "Bad HTTP response status line: ''",
        )

    def test_openssl_syscall_error(self):
        known = OpenSSL.SSL.SysCallError(EUNEXPECTEDEOF, "Unexpected EOF")
        unknown = OpenSSL.SSL.SysCallError(EPERM, "Denied")

        self.assertEqual(get_exception_reason(known), "Unexpected EOF")
        self.assertIsNone(get_exception_reason(unknown))

    def test_openssl_zero_return_error(self):
        self.assertEqual(
            get_exception_reason(OpenSSL.SSL.ZeroReturnError()),
            "OpenSSL Error: OpenSSL.SSL.ZeroReturnError",
        )

    def test_ssl_error(self):
        known = ssl.SSLError(ECONNRESET, "Connection reset")

        self.assertEqual(get_exception_reason(known), f"SSL Error: {known}")
        self.assertIsNone(get_exception_reason(ssl.SSLError(EPERM, "Denied")))

    def test_socket_error(self):
        reset = OSError(ECONNRESET, "Connection reset by peer")
        self.assertEqual(get_exception_reason(reset), str(reset))

    def test_http_request_exception(self):
        self.assertEqual(get_exception_reason(HTTPRequestException("Fail")), "Fail")

    def test_http_exception(self):
        self.assertEqual(
            get_exception_reason(http.client.IncompleteRead(b"abc")),
            "IncompleteRead: (b'abc',)",
        )

    def test_unknown_exception(self):
        self.assertIsNone(get_exception_reason(ValueError("unknown")))
