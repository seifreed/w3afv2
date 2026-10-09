"""
test_HTTPResponse.py

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
import pickle
import unittest
from random import choice

import msgpack
import pytest

from w3af.core.data.dc.headers import Headers
from w3af.core.data.misc.encoding import ESCAPED_CHAR, smart_unicode
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.url.HTTPResponse import DEFAULT_CHARSET, HTTPResponse

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

        with self.assertLogs("w3af.core.data.url.HTTPResponse", level="DEBUG") as logs:
            self.assertEqual(response.get_body(), b"body")

        self.assertIn("failed to send the CONTENT_TYPE", logs.output[0])

    def test_binary_bytes_body_is_preserved(self):
        url = URL("http://w3af.com")
        headers = Headers([("Content-Type", "application/octet-stream")])
        body = b"\x00\xff"
        response = HTTPResponse(200, body, headers, url, url, binary_response=True)
        self.assertEqual(response.get_body(), body)
        self.assertEqual(response.get_raw_body(), body)
        self.assertEqual(response.get_body_hash(), hashlib.sha256(body).hexdigest())
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
        resp = self.resp
        resp.set_charset("utf-8")
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
        self.assertEqual(True, resp.is_pdf())

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
            html = body.encode(charset)
            headers = Headers(
                [("Content-Type", f"text/xml; charset={choice(('XXX', 'utf-8'))}")]
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

        pickled_resp = pickle.dumps(resp)
        unpickled_resp = pickle.loads(pickled_resp)

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
        self.assertEqual(
            resp.get_body_hash(), hashlib.sha256(html.encode()).hexdigest()
        )

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
