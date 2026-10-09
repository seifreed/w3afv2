"""
test_global_redirect.py

Copyright 2012 Andres Riancho

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
import urllib.parse
from typing import ClassVar
from unittest import TestCase

from w3af.core.data.dc.headers import Headers
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.url.http_response import HTTPResponse
from w3af.plugins.audit.global_redirect import global_redirect
from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest

SCAN_CONFIG = {
    "cfg": {
        "target": None,
        "plugins": {
            "audit": (PluginConfig("global_redirect"),),
            "crawl": (
                PluginConfig("web_spider", ("only_forward", True, PluginConfig.BOOL)),
            ),
        },
    },
}


REDIRECT_URL = "http://redirect-site/audit/global_redirect/"

GLOBAL_REDIRECT_INDEX = """
<a href="redirect-302.py?url=/home">302</a>
<a href="redirect-header-302.py?url=/home">header 302</a>
<a href="redirect-302-filtered.py?url=/home">filtered 302</a>
<a href="redirect-javascript.py?url=/home">javascript</a>
<a href="redirect-meta.py?url=/home">meta</a>
<a href="redirect-safe.py?url=/home">safe</a>
"""


def _redirect_target(request):
    return urllib.parse.parse_qs(urllib.parse.urlsplit(request.uri).query).get(
        "url", [""]
    )[0]


def redirect_302(mock_response, request, uri, response_headers):
    target = _redirect_target(request)
    response_headers["Content-Type"] = "text/html"
    response_headers["Location"] = target
    return 302, response_headers, ""


def redirect_header_302(mock_response, request, uri, response_headers):
    target = _redirect_target(request)
    response_headers["Content-Type"] = "text/html"
    response_headers["URI"] = target
    return 302, response_headers, ""


def redirect_302_filtered(mock_response, request, uri, response_headers):
    """Only redirects to absolute http(s) URLs, local paths are kept."""
    target = _redirect_target(request)
    response_headers["Content-Type"] = "text/html"
    if target.startswith(("http://", "https://", "//")):
        response_headers["Location"] = target
        return 302, response_headers, ""
    return 200, response_headers, "<html>Staying here</html>"


def redirect_javascript(mock_response, request, uri, response_headers):
    target = _redirect_target(request)
    response_headers["Content-Type"] = "text/html"
    body = f'<html><body><script>window.location = "{target}";</script></body></html>'
    return 200, response_headers, body


def redirect_meta(mock_response, request, uri, response_headers):
    target = _redirect_target(request)
    response_headers["Content-Type"] = "text/html"
    body = (
        '<html><head><meta http-equiv="refresh" content="0; URL='
        f'{target}"></head><body>Redirecting</body></html>'
    )
    return 200, response_headers, body


def redirect_safe(mock_response, request, uri, response_headers):
    response_headers["Content-Type"] = "text/html"
    return 200, response_headers, "<html>Nothing to see here</html>"


GLOBAL_REDIRECT_PAGES = {
    "redirect-302.py": redirect_302,
    "redirect-header-302.py": redirect_header_302,
    "redirect-302-filtered.py": redirect_302_filtered,
    "redirect-javascript.py": redirect_javascript,
    "redirect-meta.py": redirect_meta,
    "redirect-safe.py": redirect_safe,
}


def global_redirect_site(mock_response, request, uri, response_headers):
    page = urllib.parse.urlsplit(request.uri).path.rsplit("/", 1)[-1]
    responder = GLOBAL_REDIRECT_PAGES.get(page)
    if responder is None:
        response_headers["Content-Type"] = "text/html"
        return 200, response_headers, GLOBAL_REDIRECT_INDEX
    return responder(mock_response, request, uri, response_headers)


class TestGlobalRedirect(PluginTest):

    target_url = REDIRECT_URL

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(re.compile(f"{re.escape(REDIRECT_URL)}.*"), global_redirect_site)
    ]

    def test_found_redirect(self):
        cfg = SCAN_CONFIG["cfg"]
        cfg["target"] = self.target_url
        self._scan(cfg["target"], cfg["plugins"])

        vulns = self.kb.get("global_redirect", "global_redirect")

        self.assertAllVulnNamesEqual("Insecure redirection", vulns)

        EXPECTED = [
            ("redirect-javascript.py", "url"),
            ("redirect-meta.py", "url"),
            ("redirect-302.py", "url"),
            ("redirect-header-302.py", "url"),
            ("redirect-302-filtered.py", "url"),
        ]

        self.assertExpectedVulnsFound(EXPECTED, vulns)


class TestGlobalRedirectBasic(PluginTest):

    target_url = "http://httpretty"

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse("http://httpretty/", '<a href="/redir?target=">redirect</a>'),
        MockResponse("http://httpretty/redir?target=", "No redirect"),
        MockResponse(
            "http://httpretty/redir?target=http://www.w3af.org/",
            status=302,
            headers={"Location": "https://www.w3af.org/"},
            body="",
        ),
    ]

    def test_original_response_has_no_redirect(self):
        cfg = SCAN_CONFIG["cfg"]
        cfg["target"] = self.target_url

        self._scan(cfg["target"], cfg["plugins"])

        vulns = self.kb.get("global_redirect", "global_redirect")
        expected = [("redir", "target")]

        self.assertAllVulnNamesEqual("Insecure redirection", vulns)
        self.assertExpectedVulnsFound(expected, vulns)


class TestGlobalRedirectBasicWithMetaRedir(PluginTest):

    target_url = "http://httpretty"

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse("http://httpretty/", '<a href="/redir?target=">redirect</a>'),
        MockResponse(
            "http://httpretty/redir?target=",
            '<meta http-equiv="refresh" content="0; url=">',
        ),
        MockResponse(
            "http://httpretty/redir?target=http://www.w3af.org/",
            body='<meta http-equiv="refresh" content="0; url=http://www.w3af.org/">',
        ),
    ]

    def test_original_response_has_meta_redirect(self):
        cfg = SCAN_CONFIG["cfg"]
        cfg["target"] = self.target_url

        self._scan(cfg["target"], cfg["plugins"])

        vulns = self.kb.get("global_redirect", "global_redirect")
        expected = [("redir", "target")]

        self.assertAllVulnNamesEqual("Insecure redirection", vulns)
        self.assertExpectedVulnsFound(expected, vulns)


class TestGlobalRedirectExtendedPayloadSet(PluginTest):

    target_url = "http://httpretty"

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse("http://httpretty/", '<a href="/redir?target=">redirect</a>'),
        MockResponse(
            "http://httpretty/redir?target=",
            status=302,
            headers={"Location": "http://httpretty/default"},
            body="",
        ),
        MockResponse(
            "http://httpretty/redir?target=//httpretty.w3af.org/",
            status=302,
            headers={"Location": "httpretty.w3af.org"},
            body="",
        ),
    ]

    def test_original_response_has_redirect(self):
        cfg = SCAN_CONFIG["cfg"]
        cfg["target"] = self.target_url

        self._scan(cfg["target"], cfg["plugins"])

        vulns = self.kb.get("global_redirect", "global_redirect")
        expected = [("redir", "target")]

        self.assertAllVulnNamesEqual("Insecure redirection", vulns)
        self.assertExpectedVulnsFound(expected, vulns)


class TestGlobalRedirectUnitExtractScript(TestCase):
    def test_extract_script_code_simple(self):
        plugin = global_redirect()

        body = "<script>var x=1;var y=2;</script>"
        url = URL("http://www.w3af.com/")
        headers = Headers([("content-type", "text/html")])
        resp = HTTPResponse(200, body, headers, url, url, _id=1)

        code = plugin._extract_script_code(resp)
        code = [c for c in code]

        self.assertEqual(code, ["var x=1", "var y=2"])

    def test_extract_script_code_new_line(self):
        plugin = global_redirect()

        body = "<script>var x=1;\nvar y=2;alert(1)</script>"
        url = URL("http://www.w3af.com/")
        headers = Headers([("content-type", "text/html")])
        resp = HTTPResponse(200, body, headers, url, url, _id=1)

        code = plugin._extract_script_code(resp)
        code = [c for c in code]

        self.assertEqual(code, ["var x=1", "var y=2", "alert(1)"])


class TestGlobalRedirectUnitJSRedirect(TestCase):
    def test_javascript_redirect_simple(self):
        plugin = global_redirect()

        body = '<script>window.location = "http://w3af.org/"</script>'
        url = URL("http://www.w3af.com/")
        headers = Headers([("content-type", "text/html")])
        resp = HTTPResponse(200, body, headers, url, url, _id=1)

        self.assertTrue(plugin._javascript_redirect(resp))

    def test_javascript_redirect_assign(self):
        plugin = global_redirect()

        body = '<script>window.location.assign("http://www.w3af.org")</script>'
        url = URL("http://www.w3af.com/")
        headers = Headers([("content-type", "text/html")])
        resp = HTTPResponse(200, body, headers, url, url, _id=1)

        self.assertTrue(plugin._javascript_redirect(resp))


class TestGlobalRedirectUnitResponseHasRedirect(TestCase):
    def test_response_has_redirect_headers(self):
        plugin = global_redirect()

        body = ""
        url = URL("http://www.w3af.com/")
        headers = Headers(
            [("content-type", "text/html"), ("Location", "http://w3af.org")]
        )
        resp = HTTPResponse(200, body, headers, url, url, _id=1)

        self.assertTrue(plugin._response_has_redirect(resp))

    def test_response_has_redirect_meta(self):
        plugin = global_redirect()

        body = '<meta http-equiv="refresh" content="0; url=">'
        url = URL("http://www.w3af.com/")
        headers = Headers([("content-type", "text/html")])
        resp = HTTPResponse(200, body, headers, url, url, _id=1)

        self.assertTrue(plugin._response_has_redirect(resp))

    def test_response_has_redirect_js_1(self):
        plugin = global_redirect()

        body = '<script>window.location.assign("http://www.w3af.org")</script>'
        url = URL("http://www.w3af.com/")
        headers = Headers([("content-type", "text/html")])
        resp = HTTPResponse(200, body, headers, url, url, _id=1)

        self.assertTrue(plugin._response_has_redirect(resp))

    def test_response_has_redirect_js_2(self):
        plugin = global_redirect()

        body = '<script>window.location.href = "http://www.w3af.org"</script>'
        url = URL("http://www.w3af.com/")
        headers = Headers([("content-type", "text/html")])
        resp = HTTPResponse(200, body, headers, url, url, _id=1)

        self.assertTrue(plugin._response_has_redirect(resp))

    def test_response_has_redirect_js_false(self):
        plugin = global_redirect()

        body = "<script>alert(window.location)</script>"
        url = URL("http://www.w3af.com/")
        headers = Headers([("content-type", "text/html")])
        resp = HTTPResponse(200, body, headers, url, url, _id=1)

        self.assertFalse(plugin._response_has_redirect(resp))

    def test_response_has_redirect_headers_false(self):
        plugin = global_redirect()

        body = '<meta generator="">'
        url = URL("http://www.w3af.com/")
        headers = Headers([("content-type", "text/html")])
        resp = HTTPResponse(200, body, headers, url, url, _id=1)

        self.assertFalse(plugin._response_has_redirect(resp))
