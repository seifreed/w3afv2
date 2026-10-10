"""
test_grep_branches.py

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

Unit tests for the grep plugin code paths that the per-plugin test modules
do not exercise (guards, error handling and reporting variations).
"""

import unittest

import w3af.core.data.kb.knowledge_base as kb
from w3af.core.data.constants import severity
from w3af.core.data.kb.info import Info
from w3af.core.data.parsers.doc.url import URL
from w3af.plugins import grep
from w3af.plugins.grep.analyze_cookies import analyze_cookies
from w3af.plugins.grep.cache_control import cache_control
from w3af.plugins.grep.click_jacking import click_jacking
from w3af.plugins.grep.code_disclosure import code_disclosure
from w3af.plugins.grep.content_sniffing import MAX_REPORTS, content_sniffing
from w3af.plugins.grep.credit_cards import credit_cards
from w3af.plugins.grep.cross_domain_js import cross_domain_js
from w3af.plugins.grep.csp import csp
from w3af.plugins.grep.error_pages import error_pages
from w3af.plugins.grep.expect_ct import expect_ct
from w3af.plugins.grep.form_autocomplete import form_autocomplete
from w3af.plugins.grep.get_emails import get_emails
from w3af.plugins.grep.hash_analysis import hash_analysis
from w3af.plugins.grep.http_auth_detect import http_auth_detect
from w3af.plugins.grep.keys import keys
from w3af.plugins.grep.lang import lang
from w3af.plugins.grep.meta_generator import meta_generator
from w3af.plugins.grep.strange_reason import strange_reason
from w3af.plugins.grep.strict_transport_security import strict_transport_security
from w3af.plugins.grep.symfony import symfony
from w3af.plugins.grep.wsdl_greper import wsdl_greper
from w3af.plugins.tests.grep.grep_test_utils import (
    GrepPluginTestCase,
    make_request,
    make_response,
)

HTTPS = "https://www.w3af.com/"


class TestGrepPackage(unittest.TestCase):
    def test_long_description(self):
        self.assertIn("Grep plugins", grep.get_long_description())


class TestAnalyzeCookiesBranches(GrepPluginTestCase):

    def setUp(self):
        super().setUp()
        self.plugin = self.configure_plugin(analyze_cookies())

    def tearDown(self):
        self.plugin.end()
        super().tearDown()

    def _grep(self, cookie, url="http://www.w3af.com/", _id=1):
        response = make_response(url, headers=[("Set-Cookie", cookie)], _id=_id)
        self.plugin.grep(make_request(url), response)

    def test_invalid_cookie_is_reported(self):
        self._grep('a"b=1')

        invalid = kb.kb.get("analyze_cookies", "invalid-cookies")
        self.assertEqual(len(invalid), 1)
        self.assertEqual(invalid[0].get_name(), "Invalid cookie")
        self.assertEqual(kb.kb.get("analyze_cookies", "cookies"), [])

    def test_fingerprint_reported_once(self):
        self._grep("PHPSESSID=abc", _id=1)
        self._grep("PHPSESSID=def", _id=2)

        fingerprints = kb.kb.get("analyze_cookies", "fingerprint")
        self.assertEqual(len(fingerprints), 1)
        self.assertEqual(fingerprints[0]["httpd"], "PHP")

    def test_unknown_cookie_is_not_fingerprinted_twice(self):
        self._grep("notaknownplatformcookie=1", _id=1)
        self._grep("notaknownplatformcookie=2", _id=2)

        self.assertEqual(kb.kb.get("analyze_cookies", "fingerprint"), [])
        self.assertIn(
            "notaknownplatformcookie", self.plugin._cookie_key_failed_fingerprint
        )

    def test_secure_cookie_from_other_domain_is_ignored(self):
        self._grep("session=0123456789abcdef; secure", url=HTTPS)

        cookie_value = "session=0123456789abcdef"
        request = make_request(
            "http://other.example/", headers=[("Cookie", cookie_value)]
        )
        self.plugin.grep(request, make_response("http://other.example/"))

        self.assertEqual(kb.kb.get("analyze_cookies", "secure_via_http"), [])


class TestCacheControlBranches(GrepPluginTestCase):

    def setUp(self):
        super().setUp()
        self.plugin = self.configure_plugin(cache_control())

    def _grep(self, response):
        self.plugin.grep(make_request(response.get_url()), response)

    def test_redirects_are_ignored(self):
        self._grep(make_response(HTTPS, code=302))
        self.plugin.end()
        self.assertEqual(kb.kb.get("cache_control", "cache_control"), [])

    def test_404_pages_are_ignored(self):
        marker = self.mark_as_404()
        self._grep(make_response(HTTPS, body=f"<html>{marker}</html>"))
        self.plugin.end()
        self.assertEqual(kb.kb.get("cache_control", "cache_control"), [])

    def test_response_without_parser(self):
        self._grep(make_response(HTTPS, body="\x00\x01", content_type="foo/bar"))
        self.plugin.end()
        self.assertEqual(len(kb.kb.get("cache_control", "cache_control")), 1)

    def test_some_urls_protected(self):
        protected = make_response(
            HTTPS + "safe",
            headers=[("Pragma", "no-cache"), ("Cache-Control", "no-store")],
            _id=1,
        )
        self._grep(protected)
        self._grep(make_response(HTTPS + "unsafe", _id=2))
        self.plugin.end()

        vulns = kb.kb.get("cache_control", "cache_control")
        self.assertEqual(len(vulns), 1)
        self.assertIn("Some URLs have no protection", vulns[0].get_desc())
        self.assertIn("unsafe", vulns[0].get_desc())


class TestClickJackingBranches(GrepPluginTestCase):

    def setUp(self):
        super().setUp()
        self.plugin = self.configure_plugin(click_jacking())

    def _grep(self, response, method="GET"):
        self.plugin.grep(make_request(response.get_url(), method=method), response)

    def _findings(self):
        self.plugin.end()
        return kb.kb.get("click_jacking", "click_jacking")

    def test_ignored_responses(self):
        marker = self.mark_as_404()
        self._grep(make_response(), method="POST")
        self._grep(make_response(code=302))
        self._grep(make_response(content_type="image/png"))
        self._grep(make_response(body=""))
        self._grep(make_response(content_type="text/javascript"))
        self._grep(make_response(content_type="text/css"))
        self._grep(make_response(content_type="application/xml"))
        self._grep(make_response(body=f"<html>{marker}</html>"))

        self.assertEqual(self._findings(), [])

    def test_all_urls_vulnerable_with_many_samples(self):
        for i in range(click_jacking.MAX_SAMPLES + 1):
            self._grep(make_response(f"http://www.w3af.com/{i}", _id=i + 1))

        findings = self._findings()
        self.assertEqual(len(findings), 1)
        self.assertIn("All the received HTTP responses", findings[0].get_desc())

    def test_some_urls_vulnerable_with_many_samples(self):
        protected = make_response(headers=[("X-Frame-Options", "DENY")], _id=1000)
        self._grep(protected)
        for i in range(click_jacking.MAX_SAMPLES):
            self._grep(make_response(f"http://www.w3af.com/{i}", _id=i + 1))

        findings = self._findings()
        self.assertEqual(len(findings), 1)
        self.assertIn("Only the first", findings[0].get_desc())

    def test_some_urls_vulnerable(self):
        protected = make_response(headers=[("X-Frame-Options", "DENY")], _id=1000)
        self._grep(protected)
        self._grep(make_response("http://www.w3af.com/frame-me", _id=1))

        findings = self._findings()
        self.assertEqual(len(findings), 1)
        self.assertIn("frame-me", findings[0].get_desc())


class TestMaxReportsLimit(GrepPluginTestCase):
    """
    The header checking plugins stop reporting after MAX_REPORTS findings.
    """

    def _assert_limited(self, plugin_klass, kb_key):
        plugin = self.configure_plugin(plugin_klass())
        for i in range(MAX_REPORTS + 5):
            url = f"https://www.w3af.com/{i}"
            plugin.grep(make_request(url), make_response(url, _id=i + 1))
        plugin.end()

        findings = kb.kb.get(plugin.get_name(), kb_key)
        self.assertEqual(len(findings), 1)
        # The plugin stops analyzing once it went over the limit
        self.assertEqual(plugin._reports, MAX_REPORTS + 1)

    def test_content_sniffing(self):
        self._assert_limited(content_sniffing, "content_sniffing")

    def test_expect_ct(self):
        self._assert_limited(expect_ct, "expect_ct")

    def test_strict_transport_security(self):
        self._assert_limited(strict_transport_security, "strict_transport_security")


class TestCodeDisclosureBranches(GrepPluginTestCase):

    def test_404_code_disclosure_reported_once(self):
        marker = self.mark_as_404()
        plugin = self.configure_plugin(code_disclosure())
        body = f"<html>{marker} <?php echo $secret; ?></html>"

        plugin.grep(make_request(), make_response(body=body, _id=1))
        plugin.grep(make_request(), make_response(body=body, _id=2))

        findings = kb.kb.get("code_disclosure", "code_disclosure")
        self.assertEqual(len(findings), 1)
        self.assertEqual(
            findings[0].get_name(), "Code disclosure vulnerability in 404 page"
        )

    def test_not_text(self):
        plugin = self.configure_plugin(code_disclosure())
        plugin.grep(make_request(), make_response(content_type="image/png"))
        self.assertEqual(kb.kb.get("code_disclosure", "code_disclosure"), [])


class TestCrossDomainJSBranches(GrepPluginTestCase):

    SCRIPT = '<script src="https://evil.example/x.js"></script>'

    def test_plugin_disabled_without_trusted_domain_file(self):
        plugin = self.configure_plugin(cross_domain_js())
        options = plugin.get_options()
        options["secure_js_file"].set_value("")
        plugin.set_options(options)

        plugin.grep(make_request(), make_response(body=self.SCRIPT))
        plugin.end()

        self.assertEqual(kb.kb.get("cross_domain_js", "cross_domain_js"), [])

    def test_not_text(self):
        plugin = self.configure_plugin(cross_domain_js())
        response = make_response(body=self.SCRIPT, content_type="image/png")
        plugin.grep(make_request(), response)
        self.assertEqual(kb.kb.get("cross_domain_js", "cross_domain_js"), [])

    def test_invalid_script_src(self):
        plugin = self.configure_plugin(cross_domain_js())
        body = '<script src="http://[::1"></script>'
        plugin.grep(make_request(), make_response(body=body))
        self.assertEqual(kb.kb.get("cross_domain_js", "cross_domain_js"), [])


class TestCSPSharedVulnerability(GrepPluginTestCase):

    def test_vulnerability_shared_by_several_urls(self):
        plugin = self.configure_plugin(csp())
        policy = ("Content-Security-Policy", "default-src *")
        for i in (1, 2):
            url = f"http://www.w3af.com/{i}"
            plugin.grep(make_request(url), make_response(url, headers=[policy], _id=i))
        plugin.end()

        vulns = kb.kb.get("csp", "csp")
        self.assertEqual(len(vulns), 1)
        self.assertEqual(sorted(vulns[0].get_id()), [1, 2])
        self.assertEqual(vulns[0].get_url().url_string, "http://www.w3af.com/")


class TestErrorPagesBranches(GrepPluginTestCase):

    def test_same_url_reported_once(self):
        plugin = self.configure_plugin(error_pages())
        body = error_pages.ERROR_PAGES[0]
        plugin.grep(make_request(), make_response(body=body, _id=1))
        plugin.grep(make_request(), make_response(body=body, _id=2))
        plugin.end()

        self.assertEqual(len(kb.kb.get("error_pages", "error_page")), 1)

    def test_url_with_other_finding_is_not_reported(self):
        plugin = self.configure_plugin(error_pages())
        plugin.grep(make_request(), make_response(body=error_pages.ERROR_PAGES[0]))

        other = Info("Other finding", "Some other finding description", 9, "x")
        other.set_url(URL("http://www.w3af.com/"))
        kb.kb.append("x", "y", other)
        plugin.end()

        self.assertEqual(kb.kb.get("error_pages", "error_page"), [])

    def test_version_numbers_in_error_pages(self):
        plugin = self.configure_plugin(error_pages())
        body = "<html><address>Apache/2.2.22 (Ubuntu) Server</address></html>"
        plugin.grep(make_request(), make_response(body=body, code=404, _id=1))
        plugin.grep(make_request(), make_response(body=body, code=500, _id=2))

        servers = kb.kb.get("error_pages", "server")
        self.assertEqual(len(servers), 1)
        self.assertIn("Apache/2.2.22", servers[0].get_desc())

    def test_not_text(self):
        plugin = self.configure_plugin(error_pages())
        body = error_pages.ERROR_PAGES[0]
        response = make_response(body=body, content_type="image/png")
        plugin.grep(make_request(), response)
        plugin.end()
        self.assertEqual(kb.kb.get("error_pages", "error_page"), [])


class TestGetEmailsBranches(GrepPluginTestCase):

    def test_sent_and_duplicated_emails_are_skipped(self):
        plugin = self.configure_plugin(get_emails())
        body = (
            '<a href="mailto:echo@w3af.com">x</a>' '<a href="mailto:a@w3af.com">y</a>'
        )
        request = make_request("http://www.w3af.com/?mail=echo@w3af.com")

        plugin.grep(request, make_response(body=body, _id=1))
        plugin.grep(request, make_response(body=body, _id=2))

        emails = {i["mail"] for i in kb.kb.get("emails", "emails")}
        self.assertEqual(emails, {"a@w3af.com"})

    def test_unparseable(self):
        plugin = self.configure_plugin(get_emails())
        response = make_response(body="\x00", content_type="foo/bar")
        plugin.grep(make_request(), response)
        self.assertEqual(kb.kb.get("emails", "emails"), [])


class TestHashAnalysis(GrepPluginTestCase):

    MD5 = "cdf13c6f85b216a18665e7bba74cc1a7"

    def test_hash_found_after_other_words(self):
        plugin = self.configure_plugin(hash_analysis())
        body = f"<html><body>The password hash is {self.MD5} ok</body></html>"
        plugin.grep(make_request(), make_response(body=body))
        plugin.grep(make_request(), make_response(body=body, _id=2))

        findings = kb.kb.get("hash_analysis", "hash_analysis")
        self.assertEqual(len(findings), 1)
        self.assertIn("MD5", findings[0].get_desc())

    def test_non_hash_tokens_are_ignored(self):
        plugin = self.configure_plugin(hash_analysis())
        not_hex = "z" * 32
        repeated = "2222222222222222222aaaaaaaaaaaaa"
        letters_only = "abcdefabcdefabcdefabcdefabcdefab"
        odd_length = "a" * 35
        body = f"{not_hex} {repeated} {letters_only} {odd_length}"
        plugin.grep(make_request(), make_response(body=body))

        self.assertEqual(kb.kb.get("hash_analysis", "hash_analysis"), [])

    def test_not_text(self):
        plugin = self.configure_plugin(hash_analysis())
        response = make_response(body=self.MD5, content_type="image/png")
        plugin.grep(make_request(), response)
        self.assertEqual(kb.kb.get("hash_analysis", "hash_analysis"), [])

    def test_long_desc(self):
        self.assertIn("hash", hash_analysis().get_long_desc())


class TestHttpAuthDetectBranches(GrepPluginTestCase):

    def test_credentials_in_url(self):
        plugin = self.configure_plugin(http_auth_detect())
        url = "http://user:pass@www.w3af.com/"
        plugin.grep(make_request(url), make_response(url))

        vulns = kb.kb.get("http_auth_detect", "userPassUri")
        self.assertEqual(len(vulns), 1)
        self.assertIn("user and password in the URI", vulns[0].get_desc())

    def test_unparseable_body(self):
        plugin = self.configure_plugin(http_auth_detect())
        plugin.grep(make_request(), self.make_unparseable_response())
        self.assertEqual(kb.kb.get("http_auth_detect", "userPassUri"), [])

    def test_ntlm_over_https(self):
        plugin = self.configure_plugin(http_auth_detect())
        response = make_response(
            HTTPS, code=401, headers=[("WWW-Authenticate", "NTLM")]
        )
        plugin.grep(make_request(HTTPS), response)

        vulns = kb.kb.get("http_auth_detect", "auth")
        self.assertEqual(len(vulns), 1)
        self.assertEqual(vulns[0].get_name(), "NTLM authentication")
        self.assertEqual(vulns[0].get_severity(), severity.LOW)


class TestLangBranches(GrepPluginTestCase):

    def test_gives_up_after_too_many_unknown_pages(self):
        plugin = self.configure_plugin(lang())
        for i in range(plugin._tries_left):
            plugin.grep(make_request(), make_response(body="1234", _id=i + 1))

        self.assertEqual(kb.kb.raw_read("lang", "lang"), "unknown")

        # Once it gave up, it stops analyzing responses
        english = "The quick brown fox jumps over the lazy dog " * 5
        plugin.grep(make_request(), make_response(body=english, _id=100))
        self.assertEqual(kb.kb.raw_read("lang", "lang"), "unknown")

    def test_404_pages_are_ignored(self):
        marker = self.mark_as_404()
        plugin = self.configure_plugin(lang())
        plugin.grep(make_request(), make_response(body=f"<html>{marker}</html>"))
        self.assertEqual(kb.kb.raw_read("lang", "lang"), [])


class TestSimpleGuards(GrepPluginTestCase):
    """
    Responses the grep plugins must ignore without reporting anything.
    """

    def test_credit_cards_non_200(self):
        plugin = self.configure_plugin(credit_cards())
        response = make_response(body="3566 0020 2036 0505", code=500)
        plugin.grep(make_request(), response)
        self.assertEqual(kb.kb.get("credit_cards", "credit_cards"), [])

    def test_keys_non_200(self):
        plugin = self.configure_plugin(keys())
        response = make_response(body="-----BEGIN RSA PRIVATE KEY-----", code=500)
        plugin.grep(make_request(), response)
        self.assertEqual(kb.kb.get("keys", "keys"), [])

    def test_wsdl_non_200(self):
        plugin = self.configure_plugin(wsdl_greper())
        body = "<definitions xmlns:soap='http://schemas.xmlsoap.org/wsdl/'>"
        plugin.grep(make_request(), make_response(body=body, code=500))
        self.assertEqual(kb.kb.get("wsdl_greper", "wsdl"), [])

    def test_strange_reason_unknown_code(self):
        plugin = self.configure_plugin(strange_reason())
        plugin.grep(make_request(), make_response(code=299))
        self.assertEqual(kb.kb.get("strange_reason", "strange_reason"), [])

    def test_meta_generator_404(self):
        marker = self.mark_as_404()
        plugin = self.configure_plugin(meta_generator())
        body = f'<html><meta name="generator" content="Joomla"/>{marker}</html>'
        plugin.grep(make_request(), make_response(body=body))
        self.assertEqual(kb.kb.get("meta_generator", "meta_generator"), [])

    def test_symfony_detection_is_remembered(self):
        plugin = self.configure_plugin(symfony())
        form = '<form><input name="x" /></form>'
        first = make_response(body=form, headers=[("Set-Cookie", "symfony=1")])
        plugin.grep(make_request(), first)

        second_url = "http://www.w3af.com/2"
        second = make_response(second_url, body=form, _id=2)
        plugin.grep(make_request(second_url), second)

        self.assertEqual(len(kb.kb.get("symfony", "symfony")), 2)

    def test_form_autocomplete_unparseable(self):
        plugin = self.configure_plugin(form_autocomplete())
        plugin.grep(make_request(), self.make_unparseable_response())
        self.assertEqual(kb.kb.get("form_autocomplete", "form_autocomplete"), [])
