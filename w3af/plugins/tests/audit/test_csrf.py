"""
test_csrf.py

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

import itertools
import re
import unittest
from typing import ClassVar

from w3af.core.data.dc.cookie import Cookie
from w3af.core.data.dc.headers import Headers
from w3af.core.data.dc.urlencoded_form import URLEncodedForm
from w3af.core.data.parsers.doc.url import URL, parse_qs
from w3af.core.data.parsers.utils.form_params import FormParameters
from w3af.core.data.request.fuzzable_request import FuzzableRequest
from w3af.core.data.url.extended_urllib import ExtendedUrllib
from w3af.core.data.url.http_response import HTTPResponse
from w3af.plugins.audit.csrf import csrf
from w3af.plugins.tests.audit.vulnerable_responses import html_page, request_param
from w3af.plugins.tests.helper import LOREM, MockResponse, PluginConfig, PluginTest

CSRF_URL = "http://mock/w3af/audit/csrf/"
ORDER_IDS = itertools.count(1000)
SESSION_COOKIE = {"Set-Cookie": "PHPSESSID=0f1e2d3c4b5a69788796a5b4c3d2e1f0"}
EXPECTED_VALUE = "cc2544ba4af772c31bc3da928e4e33a8"

INDEX_BODY = f"""
<a href="vulnerable/buy.php?shares=123">Buy</a>
<a href="vulnerable-rnd/buy.php?shares=123">Buy, random page</a>
<a href="link-vote/vote.php?id=1">Vote</a>
<a href="referer/buy.php?shares=123">Buy, referer checked</a>
<a href="token/buy.php?shares=123&amp;token={EXPECTED_VALUE}">Buy with token</a>
<a href="style.css?v=1">Style</a>
"""


def bought(shares):
    return f"<p>You bought {shares} shares.</p><p>{LOREM}</p>"


def vulnerable(request):
    return bought(request_param(request, "shares"))


def vulnerable_random(request):
    order_id = next(ORDER_IDS)
    return f"{vulnerable(request)}<p>Order {order_id}</p>"


def vote(request):
    return f"<p>Thanks for voting {request_param(request, 'id')}</p><p>{LOREM}</p>"


def referer_checked(request):
    referer = request.headers.get("Referer", CSRF_URL)
    if not referer.startswith("http://mock/"):
        return "<h1>Invalid request origin</h1>"
    return vulnerable(request)


def token_checked(request):
    if request_param(request, "token") != EXPECTED_VALUE:
        return "<h1>Invalid CSRF token</h1>"
    return vulnerable(request)


PAGES = {
    "vulnerable/buy.php": vulnerable,
    "vulnerable-rnd/buy.php": vulnerable_random,
    "link-vote/vote.php": vote,
    "referer/buy.php": referer_checked,
    "token/buy.php": token_checked,
    "secure-replay-allowed/buy.php": token_checked,
    "vulnerable-token-ignored/buy.php": vulnerable,
}


def csrf_site(mock_response, request, uri, response_headers):
    response_headers.update(SESSION_COOKIE)
    page = request.uri.removeprefix(CSRF_URL).split("?")[0]

    if page == "":
        return html_page(response_headers, INDEX_BODY)
    if page == "style.css":
        response_headers["Content-Type"] = "text/css"
        return 200, response_headers, "body { color: black; }"
    if page in PAGES:
        return html_page(response_headers, PAGES[page](request))
    return html_page(response_headers, "Not found", status=404)


class TestCSRF(PluginTest):

    target_url = CSRF_URL

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(re.compile(f"{CSRF_URL}.*"), csrf_site),
        MockResponse(re.compile(f"{CSRF_URL}.*"), csrf_site, method="POST"),
    ]

    _run_configs: ClassVar[dict] = {
        "cfg": {
            "target": target_url,
            "plugins": {
                "audit": (PluginConfig("csrf"),),
                "crawl": (
                    PluginConfig(
                        "web_spider", ("only_forward", True, PluginConfig.BOOL)
                    ),
                ),
            },
        }
    }

    def setUp(self):
        super().setUp()
        self.csrf_plugin = csrf()
        self.uri_opener = ExtendedUrllib()
        self.uri_opener.settings.set_proxy(
            self.canned_server.host, self.canned_server.port
        )
        self.csrf_plugin.set_url_opener(self.uri_opener)
        self.addCleanup(self.uri_opener.end)

    def test_found_csrf(self):
        expected = [
            "/w3af/audit/csrf/vulnerable/buy.php",
            "/w3af/audit/csrf/vulnerable-rnd/buy.php",
            "/w3af/audit/csrf/link-vote/vote.php",
        ]

        cfg = self._run_configs["cfg"]
        self._scan(cfg["target"], cfg["plugins"])

        vulns = self.kb.get("csrf", "csrf")

        self.assertEqual(set(expected), {v.get_url().get_path() for v in vulns})
        self.assertTrue(all("CSRF vulnerability" == v.get_name() for v in vulns))

    def test_resp_is_equal(self):
        url = URL("http://www.w3af.com/")
        headers = Headers([("content-type", "text/html")])

        r1 = HTTPResponse(200, "body", headers, url, url)
        r2 = HTTPResponse(404, "body", headers, url, url)
        self.assertFalse(self.csrf_plugin._is_resp_equal(r1, r2))

        r1 = HTTPResponse(200, "a", headers, url, url)
        r2 = HTTPResponse(200, "b", headers, url, url)
        self.assertFalse(self.csrf_plugin._is_resp_equal(r1, r2))

        r1 = HTTPResponse(200, "a", headers, url, url)
        r2 = HTTPResponse(200, "a", headers, url, url)
        self.assertTrue(self.csrf_plugin._is_resp_equal(r1, r2))

    def test_is_suitable(self):
        # False because no cookie is set and no QS nor post-data
        url = URL("http://www.w3af.com/")
        headers = Headers([("content-type", "text/html")])
        res = HTTPResponse(200, "body", headers, url, url)

        req = FuzzableRequest(URL("http://mock/"), method="GET")
        self.assertFalse(self.csrf_plugin._is_suitable(req, res))

        # False because no cookie is set
        req = FuzzableRequest(URL("http://mock/?id=3"), method="GET")
        self.assertFalse(self.csrf_plugin._is_suitable(req, res))

        self.uri_opener.GET(URL(CSRF_URL))

        # False because there is no QS nor post-data
        req = FuzzableRequest(URL("http://mock/"), method="GET")
        self.assertFalse(self.csrf_plugin._is_suitable(req, res))

        # False because of strict mode and a GET request
        self.csrf_plugin._strict_mode = True
        req = FuzzableRequest(URL("http://mock/?id=3"), method="GET")
        self.assertFalse(self.csrf_plugin._is_suitable(req, res))

        # False because there is no post-data
        req = FuzzableRequest(
            URL("http://mock/"), method="POST", post_data=URLEncodedForm()
        )
        self.assertFalse(self.csrf_plugin._is_suitable(req, res))

        form_params = FormParameters()
        form_params.add_field_by_attr_items([("name", "test"), ("type", "text")])
        form = URLEncodedForm(form_params)
        req = FuzzableRequest(URL("http://mock/"), method="POST", post_data=form)
        self.assertTrue(self.csrf_plugin._is_suitable(req, res))

        self.csrf_plugin._strict_mode = False

        req = FuzzableRequest(URL("http://mock/?id=3"), method="GET")
        self.assertTrue(self.csrf_plugin._is_suitable(req, res))

        # False because style sheets are not CSRF targets
        css_headers = Headers([("content-type", "text/css")])
        css = HTTPResponse(200, "body {}", css_headers, url, url)
        self.assertFalse(self.csrf_plugin._is_suitable(req, css))

    def send_with_referer(self, page):
        url = URL(f"{CSRF_URL}{page}?shares=123")
        headers = Headers([("Referer", CSRF_URL)])
        freq = FuzzableRequest(url, method="GET", headers=headers)
        return freq, self.uri_opener.send_mutant(freq)

    def test_is_origin_checked_true(self):
        freq, orig_response = self.send_with_referer("referer/buy.php")
        origin_checked = self.csrf_plugin._is_origin_checked(freq, orig_response, None)
        self.assertTrue(origin_checked)

    def test_is_origin_checked_false(self):
        freq, orig_response = self.send_with_referer("vulnerable-rnd/buy.php")
        origin_checked = self.csrf_plugin._is_origin_checked(freq, orig_response, None)
        self.assertFalse(origin_checked)

    def token_checked(self, page):
        generator = URL(f"{CSRF_URL}{page}?shares=1&token={EXPECTED_VALUE}")
        http_response = self.uri_opener.GET(generator)
        cookie = Cookie.from_http_response(http_response)
        freq = FuzzableRequest(generator, cookie=cookie)
        original_response = self.uri_opener.send_mutant(freq)

        token = {"token": EXPECTED_VALUE}
        return self.csrf_plugin._is_token_checked(freq, token, original_response)

    def test_is_token_checked_true(self):
        self.assertTrue(self.token_checked("secure-replay-allowed/buy.php"))

    def test_is_token_checked_false(self):
        """
        This covers the case where there is a token but for some reason it
        is NOT verified by the web application.
        """
        self.assertFalse(self.token_checked("vulnerable-token-ignored/buy.php"))


class TestLowLevelCSRF(unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.csrf_plugin = csrf()

    def test_shannon_entropy(self):
        self.assertEqual(0, self.csrf_plugin.shannon_entropy(b""))
        self.assertEqual(0, self.csrf_plugin.shannon_entropy(b"aaaa"))
        self.assertEqual(2, self.csrf_plugin.shannon_entropy(b"abcd"))

    def test_is_csrf_token_true_case01(self):
        self.assertTrue(
            self.csrf_plugin.is_csrf_token("token", "f842eb01b87a8ee18868d3bf80a558f3")
        )

    def test_is_csrf_token_true_case02(self):
        self.assertTrue(
            self.csrf_plugin.is_csrf_token("secret", "f842eb01b87a8ee18868d3bf80a558f3")
        )

    def test_is_csrf_token_true_case03(self):
        self.assertTrue(
            self.csrf_plugin.is_csrf_token("csrf", "f842eb01b87a8ee18868d3bf80a558f3")
        )

    def test_is_csrf_token_false_case01(self):
        self.assertFalse(self.csrf_plugin.is_csrf_token("token", ""))

    def test_is_csrf_token_false_case02(self):
        self.assertFalse(self.csrf_plugin.is_csrf_token("secret", "aaaaaaaaaa"))

    def test_is_csrf_token_false_case03(self):
        self.assertFalse(self.csrf_plugin.is_csrf_token("secret", "abababababab"))

    def test_is_csrf_token_false_case04(self):
        self.assertFalse(self.csrf_plugin.is_csrf_token("secret", "hello hello"))

    def test_is_csrf_token_false_long(self):
        self.assertFalse(self.csrf_plugin.is_csrf_token("secret", "A" * 513))

    def test_is_csrf_token_false_string_special_chars(self):
        self.assertFalse(self.csrf_plugin.is_csrf_token("secret", "áÄé"))

    def test_is_csrf_token_false_unicode(self):
        self.assertFalse(self.csrf_plugin.is_csrf_token("secret", "áÄé"))

    def test_is_csrf_token_false_case05(self):
        self.assertTrue(self.csrf_plugin.is_csrf_token("secret", LOREM[:256]))

    def test_is_csrf_token_false_case06(self):
        self.assertFalse(self.csrf_plugin.is_csrf_token("token", "f842e"))

    def test_find_csrf_token_true_simple(self):
        url = URL("http://moth/w3af/audit/csrf/")
        query_string = parse_qs("secret=f842eb01b87a8ee18868d3bf80a558f3")
        freq = FuzzableRequest(url, method="GET")
        freq.set_querystring(query_string)

        token = self.csrf_plugin._find_csrf_token(freq)
        self.assertIn("secret", token)

    def test_find_csrf_token_true_repeated(self):
        url = URL("http://moth/w3af/audit/csrf/")
        query_string = parse_qs(
            "secret=f842eb01b87a8ee18868d3bf80a558f3" "&secret=not a token"
        )
        freq = FuzzableRequest(url, method="GET")
        freq.set_querystring(query_string)

        token = self.csrf_plugin._find_csrf_token(freq)
        self.assertIn("secret", token)

    def test_find_csrf_token_false(self):
        url = URL("http://moth/w3af/audit/csrf/")
        query_string = parse_qs("secret=not a token")
        freq = FuzzableRequest(url, method="GET")
        freq.set_querystring(query_string)

        token = self.csrf_plugin._find_csrf_token(freq)
        self.assertIn("secret", token)
