"""Validation, conversions and wire dumps of FuzzableRequest."""

import unittest

from w3af.core.data.dc.cookie import Cookie
from w3af.core.data.dc.headers import Headers
from w3af.core.data.dc.json_container import JSONContainer
from w3af.core.data.dc.urlencoded_form import URLEncodedForm
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.request.empty_request import EmptyFuzzableRequest
from w3af.core.data.request.fuzzable_request import FuzzableRequest
from w3af.core.data.url.http_request import HTTPRequest
from w3af.core.data.url.http_response import HTTPResponse
from w3af.core.exceptions import BaseFrameworkException

URL_ = URL("http://w3af.org/a?b=1")


class TestConstructorValidation(unittest.TestCase):
    def test_invalid_cookie(self):
        self.assertRaises(TypeError, FuzzableRequest, URL_, cookie="a=1")

    def test_invalid_post_data(self):
        self.assertRaises(TypeError, FuzzableRequest, URL_, post_data="a=1")

    def test_invalid_headers(self):
        self.assertRaises(TypeError, FuzzableRequest, URL_, headers=[("a", "b")])


class TestAlternativeConstructors(unittest.TestCase):
    def test_from_http_response_keeps_cookies(self):
        headers = Headers([("Set-Cookie", "session=1")])
        response = HTTPResponse(200, "", headers, URL_, URL_)

        freq = FuzzableRequest.from_http_response(response)

        self.assertEqual(freq.get_uri(), URL_)
        self.assertEqual(freq.get_method(), "GET")
        self.assertEqual(str(freq.get_cookie()), "session=1")

    def test_from_http_request(self):
        request = HTTPRequest(
            URL("http://w3af.org/"),
            data="a=1",
            headers=Headers([("Content-Type", URLEncodedForm.ENCODING)]),
            method="POST",
        )
        request.add_unredirected_header("X-Unredirected", "yes")

        freq = FuzzableRequest.from_http_request(request)

        self.assertEqual(freq.get_method(), "POST")
        self.assertIsInstance(freq.get_raw_data(), URLEncodedForm)
        self.assertEqual(freq.get_headers()["X-unredirected"], "yes")


class TestSetters(unittest.TestCase):
    def setUp(self):
        self.freq = FuzzableRequest(URL_)

    def test_hash_depends_on_uri_and_data(self):
        self.assertEqual(hash(self.freq), hash(FuzzableRequest(URL_)))
        self.assertNotEqual(
            hash(self.freq), hash(FuzzableRequest(URL("http://w3af.org/")))
        )

    def test_set_url(self):
        self.freq.set_url(URL("http://w3af.org/a b"))

        self.assertEqual(self.freq.get_url().url_string, "http://w3af.org/a%20b")
        self.assertEqual(self.freq.get_uri(), self.freq.get_url())
        self.assertRaises(TypeError, self.freq.set_url, "http://w3af.org/")

    def test_force_fuzzing_url_parts_validation(self):
        self.assertRaises(TypeError, self.freq.set_force_fuzzing_url_parts, None)
        self.assertRaises(TypeError, self.freq.set_force_fuzzing_url_parts, 1)

    def test_set_referer(self):
        self.freq.set_referer(URL("http://w3af.org/ref"))

        self.assertEqual(self.freq.get_headers()["Referer"], "http://w3af.org/ref")

    def test_set_cookie(self):
        self.freq.set_cookie("a=1")
        self.assertEqual(str(self.freq.get_cookie()), "a=1")

        self.freq.set_cookie(None)
        self.assertEqual(self.freq.get_cookie(), Cookie())

        self.assertRaises(BaseFrameworkException, self.freq.set_cookie, 1)

    def test_set_data_validation(self):
        self.assertRaises(TypeError, self.freq.set_data, "a=1")


class TestWireHeaders(unittest.TestCase):
    def test_post_data_headers_override_case_insensitively(self):
        post_data = JSONContainer('{"a": 1}')
        headers = Headers([("content-type", "text/plain")])
        freq = FuzzableRequest(
            URL_, method="POST", headers=headers, post_data=post_data
        )

        all_headers = freq.get_all_headers()

        self.assertEqual(all_headers["content-type"], "application/json")
        self.assertNotIn("Content-Type", list(all_headers.keys()))

    def test_dump_ignoring_headers(self):
        headers = Headers([("Cookie", "a=1"), ("Accept", "*/*")])
        freq = FuzzableRequest(URL_, headers=headers)

        dump = freq.dump(ignore_headers=("cookie", "missing")).decode("utf-8")

        self.assertNotIn("Cookie", dump)
        self.assertIn("Accept: */*", dump)

    def test_http_request_dump_headers(self):
        request = HTTPRequest(URL_, headers=Headers([("Accept", "*/*")]))

        self.assertIn("Accept: */*", request.dump_headers())

    def test_request_hash(self):
        self.assertEqual(
            FuzzableRequest(URL_).get_request_hash(),
            FuzzableRequest(URL_).get_request_hash(),
        )


class TestEmptyFuzzableRequest(unittest.TestCase):
    def test_set_uri(self):
        freq = EmptyFuzzableRequest()
        freq.set_uri(URL_)

        self.assertEqual(freq.get_uri(), URL_)
