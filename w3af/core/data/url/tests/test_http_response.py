"""
test_http_response.py

Copyright 2011 Andres Riancho

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
import unittest
import urllib.error
import urllib.request

import msgpack
import pytest

from w3af.core.data.dc.headers import Headers
from w3af.core.data.misc.encoding import ESCAPED_CHAR, smart_unicode
from w3af.core.data.misc.serialize import dumps, loads
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.url.http_response import (
    DEFAULT_CHARSET,
    DEFAULT_WAIT_TIME,
    HTTPResponse,
)
from w3af.core.data.url.tests.helpers.route_server import Response, RouteServer

TEST_RESPONSES = {
    "hebrew": ("ולהכיר טוב יותר את המוסכמות, האופי", "Windows-1255"),
    "japanese": ("頴英 衛詠鋭液疫 益駅悦謁越榎厭円", "EUC-JP"),
    "russian": ("Вы действительно хотите удалить? Данное действие", "Windows-1251"),
    "hungarian": ("Üdvözöljük a SZTAKI webkeresőjében", "ISO-8859-2"),
    "greek": ("Παρακαλούμε πριν προχωρήσετε καταχώρηση", "ISO-8859-7"),
}


@pytest.mark.smoke
class TestHTTPResponse(unittest.TestCase):

    def setUp(self):
        self.resp = self.create_resp(Headers([("Content-Type", "text/html")]))

    def create_resp(self, headers, body="body"):
        url = URL("http://w3af.com")
        return HTTPResponse(200, body, headers, url, url)

    def test_unicode_body_no_charset(self):
        self.assertEqual(self.resp.get_body(), "body")
        self.assertEqual(self.resp.get_charset(), DEFAULT_CHARSET)

    def test_bytes_body_decodes_with_content_type_charset(self):
        headers = Headers([("Content-Type", "text/html; charset=utf-8")])
        response = self.create_resp(headers, "café".encode())
        self.assertEqual(response.get_body(), "café")
        self.assertEqual(response.get_charset(), "utf-8")

    def test_missing_content_type_is_logged(self):
        response = self.create_resp(Headers(), b"body")

        with self.assertLogs("w3af.core.data.url.http_response", level="DEBUG") as logs:
            self.assertEqual(response.get_body(), b"body")

        self.assertIn("failed to send the CONTENT_TYPE", logs.output[0])

    def test_binary_bytes_body_is_preserved(self):
        url = URL("http://w3af.com")
        headers = Headers([("Content-Type", "application/octet-stream")])
        body = b"\x00\xff"
        response = HTTPResponse(200, body, headers, url, url, binary_response=True)
        self.assertEqual(response.get_body(), body)
        self.assertEqual(response.get_raw_body(), body)
        restored = HTTPResponse.from_dict(response.to_dict())
        self.assertEqual(restored.get_body(), body)
        self.assertEqual(restored.get_raw_body(), body)

    def test_dump_decodes_bytes_for_text_output(self):
        headers = Headers([("Content-Type", "text/html; charset=utf-8")])
        response = self.create_resp(headers, "café".encode())
        self.assertIn("\r\n\r\ncafé", response.dump())

    def test_raw_read_is_none(self):
        """
        Guarantee that the '_raw_body' attr is set to None after
        used (Memory optimization)
        """
        url = URL("http://w3af.com")
        headers = Headers([("Content-Type", "text/html")])
        resp = HTTPResponse(200, "body", headers, url, url, charset="utf-8")
        # Use the 'raw body'
        _ = resp.get_body()
        self.assertEqual(resp._raw_body, None)

    def test_doc_type(self):

        # Text or HTML
        text_or_html_mime_types = (
            "application/javascript",
            "text/html",
            "text/xml",
            "text/cmd",
            "text/css",
            "text/csv",
            "text/javascript",
            "text/plain",
        )
        for mimetype in text_or_html_mime_types:
            resp = self.create_resp(Headers([("Content-Type", mimetype)]))
            self.assertEqual(
                True,
                resp.is_text_or_html(),
                f"MIME type '{mimetype}' wasn't recognized as a valid "
                f"'{HTTPResponse.DOC_TYPE_TEXT_OR_HTML}' type",
            )

        # PDF
        resp = self.create_resp(Headers([("Content-Type", "application/pdf")]))
        self.assertEqual(resp.doc_type, HTTPResponse.DOC_TYPE_PDF)

        # SWF
        resp = self.create_resp(
            Headers([("Content-Type", "application/x-shockwave-flash")])
        )
        self.assertEqual(True, resp.is_swf())

        # Image
        image_mime_types = (
            "image/gif",
            "image/jpeg",
            "image/pjpeg",
            "image/png",
            "image/tiff",
            "image/svg+xml",
            "image/vnd.microsoft.icon",
        )
        for mimetype in image_mime_types:
            resp = self.create_resp(Headers([("Content-Type", mimetype)]))
            self.assertEqual(
                True,
                resp.is_image(),
                f"MIME type '{mimetype}' wasn't recognized as a valid "
                f"'{HTTPResponse.DOC_TYPE_IMAGE}' type",
            )

    def test_parse_response_with_charset_in_both_headers(self):
        # Ensure that the responses' bodies are correctly decoded (charset in
        # both the http and html). Only http charset is expected to be used.
        for body, charset in list(TEST_RESPONSES.values()):
            hvalue = f"text/html; charset={charset}"
            body = (
                '<meta http-equiv=Content-Type content="text/html;'
                'charset=utf-16"/>' + body
            )
            htmlbody = body.encode(charset)
            resp = self.create_resp(Headers([("Content-Type", hvalue)]), htmlbody)
            self.assertEqual(body, resp.get_body())

    def test_parse_response_with_charset_in_meta_header(self):
        # Ensure responses' bodies are correctly decoded (charset only
        # in the html meta header)
        for body, charset in list(TEST_RESPONSES.values()):
            body = (
                '<meta http-equiv=Content-Type content="text/html;'
                f'charset={charset}"/>'
            )
            htmlbody = body.encode(charset)
            resp = self.create_resp(Headers(), htmlbody)
            self.assertEqual(body, resp.body)

    def test_parse_response_with_no_charset_in_header(self):
        # No charset was specified, use the default as well as the default
        # error handling scheme
        for body, charset in list(TEST_RESPONSES.values()):
            html = body.encode(charset)
            resp = self.create_resp(Headers([("Content-Type", "text/xml")]), html)
            self.assertEqual(
                smart_unicode(
                    html, DEFAULT_CHARSET, ESCAPED_CHAR, on_error_guess=False
                ),
                resp.body,
            )

    def test_parse_response_with_wrong_charset(self):
        # A wrong or non-existant charset was set; try to decode the response
        # using the default charset and handling scheme
        for body, charset in list(TEST_RESPONSES.values()):
            for wrong_charset in ("XXX", "utf-8"):
                html = body.encode(charset)
                headers = Headers(
                    [("Content-Type", f"text/xml; charset={wrong_charset}")]
                )
                resp = self.create_resp(headers, html)
                self.assertEqual(
                    smart_unicode(
                        html, DEFAULT_CHARSET, ESCAPED_CHAR, on_error_guess=False
                    ),
                    resp.body,
                )

    def test_get_lower_case_headers(self):
        headers = Headers([("Content-Type", "text/html")])
        lcase_headers = Headers([("content-type", "text/html")])

        resp = self.create_resp(headers, "<html/>")

        self.assertEqual(resp.get_lower_case_headers(), lcase_headers)
        self.assertIn("content-type", resp.get_lower_case_headers())

    def test_pickleable_http_response(self):
        html = "header <b>ABC</b>-<b>DEF</b>-<b>XYZ</b> footer"
        headers = Headers([("Content-Type", "text/html")])
        resp = self.create_resp(headers, html)

        pickled_resp = dumps(resp)
        unpickled_resp = loads(pickled_resp)

        self.assertEqual(unpickled_resp, resp)

    def test_from_dict(self):
        html = "header <b>ABC</b>-<b>DEF</b>-<b>XYZ</b> footer"
        headers = Headers([("Content-Type", "text/html")])
        orig_resp = self.create_resp(headers, html)

        msg = msgpack.dumps(orig_resp.to_dict())
        loaded_dict = msgpack.loads(msg)

        loaded_resp = HTTPResponse.from_dict(loaded_dict)

        self.assertEqual(orig_resp, loaded_resp)

        cmp_attrs = list(orig_resp.__slots__)
        cmp_attrs.remove("_body_lock")

        self.assertEqual(
            {k: getattr(orig_resp, k) for k in cmp_attrs},
            {k: getattr(loaded_resp, k) for k in cmp_attrs},
        )

    def test_from_dict_encodings(self):
        for body, charset in list(TEST_RESPONSES.values()):
            html = body.encode(charset)
            resp = self.create_resp(Headers([("Content-Type", "text/xml")]), html)

            msg = msgpack.dumps(resp.to_dict())
            loaded_dict = msgpack.loads(msg)

            loaded_resp = HTTPResponse.from_dict(loaded_dict)

            self.assertEqual(
                smart_unicode(
                    html, DEFAULT_CHARSET, ESCAPED_CHAR, on_error_guess=False
                ),
                loaded_resp.body,
            )

    def test_not_None(self):
        url = URL("http://w3af.com")
        headers = Headers([("Content-Type", "application/pdf")])
        body = None
        self.assertRaises(TypeError, HTTPResponse, 200, body, headers, url, url)

    def test_dump_response_head_3661(self):
        """
        :see: https://github.com/andresriancho/w3af/issues/3661
        """
        url = URL("http://w3af.com")
        # '\xf3' is o-tilde in windows-1251
        #
        # We get from that arbitrary character to o-tilde in windows-1251 when
        # we fail to decode it, and chardet guesses the encoding.
        headers = Headers([("Content-Type", "\xf3")])
        resp = HTTPResponse(200, "", headers, url, url)

        # '\xc3\xb3' is o-tilde in utf-8
        expected_dump = b"HTTP/1.1 200 OK\r\nContent-Type: \xc3\xb3\r\n"

        self.assertEqual(resp.dump_response_head(), expected_dump)

    def test_dump_response_head_5416(self):
        """
        :see: https://github.com/andresriancho/w3af/issues/5416
        """
        url = URL("http://w3af.com")
        headers = Headers()
        msg = "D\xe9plac\xe9 Temporairement"
        resp = HTTPResponse(200, "", headers, url, url, msg=msg)

        expected_dump = "HTTP/1.1 200 Déplacé Temporairement\r\n".encode()

        self.assertEqual(resp.dump_response_head(), expected_dump)

    def test_http_response_get_hash(self):
        html = "<html>hello world</html>"
        headers = Headers(
            [("Content-Type", "text/html"), ("Date", "2019-02-02 10:11:12 am")]
        )
        resp = self.create_resp(headers, html)

        expected = hashlib.sha256(
            resp.dump_response_head() + html.encode(DEFAULT_CHARSET)
        ).hexdigest()
        self.assertEqual(resp.get_hash(), expected)

    def test_dump_headers_exclude(self):
        html = "<html>hello world</html>"
        headers = Headers(
            [("Content-Type", "text/html"), ("Date", "2019-02-02 10:11:12 am")]
        )
        resp = self.create_resp(headers, html)

        header_dump = resp.dump_headers(exclude_headers={"date"})
        self.assertEqual(header_dump, "Content-Type: text/html\r\n")

        header_dump = resp.dump_headers(exclude_headers={})
        self.assertEqual(
            header_dump, "Content-Type: text/html\r\nDate: 2019-02-02 10:11:12 am\r\n"
        )


class TestHTTPResponseAPI(unittest.TestCase):

    URL = URL("http://w3af.com/a/b.html")

    def create_resp(self, headers=None, body="body", **kwargs):
        headers = (
            Headers([("Content-Type", "text/html")]) if headers is None else headers
        )
        return HTTPResponse(200, body, headers, self.URL, self.URL, **kwargs)

    def test_constructor_validates_types(self):
        url = self.URL
        headers = Headers()

        self.assertRaises(TypeError, HTTPResponse, 200, "", headers, "u", url)
        self.assertRaises(TypeError, HTTPResponse, 200, "", headers, url, "u")
        self.assertRaises(TypeError, HTTPResponse, 200, "", {}, url, url)
        self.assertRaises(TypeError, HTTPResponse, 200, 1, headers, url, url)

    def test_from_httplib_resp_without_original_url(self):
        server = RouteServer.serve_for(self, {"/": Response(200, "hello")})

        with urllib.request.build_opener().open(server.url()) as httplib_resp:
            resp = HTTPResponse.from_httplib_resp(httplib_resp)

        self.assertEqual(resp.get_code(), 200)
        self.assertEqual(resp.get_body(), "hello")
        self.assertEqual(resp.get_uri().url_string, server.url())
        self.assertEqual(resp.get_wait_time(), DEFAULT_WAIT_TIME)

    def test_from_httplib_resp_http_error(self):
        server = RouteServer.serve_for(self, {})

        with self.assertRaises(urllib.error.HTTPError) as raised:
            urllib.request.build_opener().open(server.url("/missing"))

        error = raised.exception
        self.addCleanup(error.close)
        resp = HTTPResponse.from_httplib_resp(error, original_url=URL(server.url()))

        self.assertEqual(resp.get_code(), 404)
        self.assertEqual(resp.get_body(), "Not Found")
        self.assertEqual(resp.get_charset(), "utf-8")

    def test_eq_attrs_and_equality(self):
        resp = self.create_resp(_id=1)

        self.assertIn("_body", resp.get_eq_attrs())
        self.assertEqual(resp, self.create_resp(_id=1))
        self.assertNotEqual(resp, self.create_resp(_id=2))

    def test_contains(self):
        resp = self.create_resp(body="hello world")

        self.assertIn("world", resp)
        self.assertNotIn("moon", resp)

    def test_repr(self):
        self.assertEqual(
            repr(self.create_resp()), "<HTTPResponse | 200 | http://w3af.com/a/b.html>"
        )

        resp = self.create_resp(_id=3)
        resp.set_from_cache(True)
        self.assertEqual(
            repr(resp),
            "<HTTPResponse | 200 | http://w3af.com/a/b.html | id:3 | fcache:True>",
        )

    def test_set_body(self):
        resp = self.create_resp()

        resp.body = "new"
        self.assertEqual(resp.get_body(), "new")

        resp.set_body(b"raw")
        self.assertEqual(resp.get_body(), "raw")

        self.assertRaises(TypeError, resp.set_body, 1)

    def test_get_body_length(self):
        # The raw body length is used while the body was not decoded
        self.assertEqual(self.create_resp(body="abc").get_body_length(), 3)

        # Then the content-length header
        headers = Headers([("Content-Type", "text/html"), ("Content-Length", "10")])
        resp = self.create_resp(headers, body="abc")
        resp.get_body()
        self.assertEqual(resp.get_body_length(), 10)

        # And finally the decoded body
        resp = self.create_resp(body="abcd")
        resp.get_body()
        self.assertEqual(resp.get_body_length(), 4)

    def test_get_clear_text_body(self):
        resp = self.create_resp(body="<html><body><p>clear text</p></body></html>")
        self.assertEqual(resp.get_clear_text_body().strip(), "clear text")

    def test_get_clear_text_body_without_parser(self):
        headers = Headers([("Content-Type", "image/png")])
        resp = self.create_resp(headers, body=b"\x89PNG")

        self.assertIsNone(resp.get_parser())
        self.assertEqual(resp.get_clear_text_body(), "")

    def test_redirect_urls(self):
        redirected = URL("http://w3af.com/c.html")
        resp = HTTPResponse(200, "", Headers(), redirected, self.URL)

        self.assertEqual(resp.get_redir_url(), redirected)
        self.assertEqual(resp.get_redir_uri(), redirected)
        self.assertTrue(resp.was_redirected())
        self.assertFalse(self.create_resp().was_redirected())

    def test_doc_types(self):
        for content_type, doc_type in (
            ("image/png", HTTPResponse.DOC_TYPE_IMAGE),
            ("application/pdf", HTTPResponse.DOC_TYPE_PDF),
            ("application/x-shockwave-flash", HTTPResponse.DOC_TYPE_SWF),
            ("application/octet-stream", HTTPResponse.DOC_TYPE_OTHER),
        ):
            resp = self.create_resp(Headers([("Content-Type", content_type)]))
            self.assertEqual(resp.doc_type, doc_type)
            self.assertEqual(resp.content_type, content_type)

        self.assertTrue(
            self.create_resp(Headers([("Content-Type", "image/gif")])).is_image()
        )
        self.assertTrue(
            self.create_resp(
                Headers([("Content-Type", "application/x-shockwave-flash")])
            ).is_swf()
        )
        self.assertEqual(self.create_resp(Headers()).content_type, "")

    def test_set_url_and_uri(self):
        resp = self.create_resp()
        uri = URL("http://w3af.com/x.html?id=1")

        self.assertRaises(TypeError, resp.set_url, "http://w3af.com/")
        self.assertRaises(TypeError, resp.set_uri, "http://w3af.com/")

        resp.set_url(uri)
        self.assertEqual(resp.get_url(), URL("http://w3af.com/x.html"))

        resp.set_uri(uri)
        self.assertEqual(resp.get_uri(), uri)
        self.assertEqual(resp.get_url(), URL("http://w3af.com/x.html"))

    def test_metadata_accessors(self):
        resp = self.create_resp()

        resp.set_wait_time(1.5)
        resp.set_alias("alias")
        resp.set_debugging_id("did")

        self.assertEqual(resp.get_wait_time(), 1.5)
        self.assertEqual(resp.get_alias(), "alias")
        self.assertEqual(resp.get_debugging_id(), "did")
        self.assertEqual(resp.info(), resp.get_headers())
        self.assertEqual(resp.get_status_line(), "HTTP/1.1 200 OK\r\n")

    def test_dump_binary_body(self):
        headers = Headers([("Content-Type", "application/octet-stream")])
        resp = self.create_resp(headers, body=b"bin\xff")

        self.assertEqual(
            resp.dump(),
            "HTTP/1.1 200 OK\r\nContent-Type: application/octet-stream\r\n\r\nbin�",
        )

    def test_redirect_destination(self):
        resp = self.create_resp(
            Headers([("Location", "  /other.html "), ("uri", "/ignored.html")])
        )
        self.assertEqual(
            resp.get_redirect_destination(), URL("http://w3af.com/other.html")
        )

        resp = self.create_resp(Headers([("URI", "/from-uri.html")]))
        self.assertEqual(
            resp.get_redirect_destination(), URL("http://w3af.com/from-uri.html")
        )

        self.assertIsNone(self.create_resp().get_redirect_destination())

    def test_redirect_destination_invalid_location(self):
        resp = self.create_resp(Headers([("Location", "http://[invalid")]))
        self.assertIsNone(resp.get_redirect_destination())

    def test_does_redirect_outside_target(self):
        def redirect_to(location):
            return self.create_resp(Headers([("Location", location)]))

        self.assertFalse(self.create_resp().does_redirect_outside_target())
        self.assertFalse(redirect_to("/x.html").does_redirect_outside_target())
        self.assertTrue(
            redirect_to("https://w3af.com/x.html").does_redirect_outside_target()
        )
        self.assertTrue(
            redirect_to("http://evil.com/x.html").does_redirect_outside_target()
        )

    def test_copy(self):
        resp = self.create_resp(_id=7)
        resp_copy = resp.copy()

        self.assertIsNot(resp, resp_copy)
        self.assertEqual(resp, resp_copy)
