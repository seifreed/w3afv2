"""
test_bruteforce_plugins.py

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

Unit tests for the bruteforce plugins which do not need a full scan.
"""

import unittest

import w3af.core.data.kb.knowledge_base as kb
from w3af.core.data.kb.info import Info
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.request.fuzzable_request import FuzzableRequest
from w3af.core.filesystem import create_temp_dir
from w3af.plugins.bruteforce import get_long_description
from w3af.plugins.bruteforce.basic_auth import basic_auth
from w3af.plugins.bruteforce.form_auth import FailedLoginPage


class TestBruteforcePackage(unittest.TestCase):
    def test_long_description(self):
        self.assertIn("Bruteforce plugins", get_long_description())


class TestBasicAuth(unittest.TestCase):
    def setUp(self):
        create_temp_dir()
        kb.kb.cleanup()

    def tearDown(self):
        kb.kb.cleanup()

    def test_audit_skips_url_without_basic_auth(self):
        plugin = basic_auth()
        plugin.set_knowledge_base(kb.kb)

        # http_auth_detect did not report this URL, so audit() returns early
        plugin.audit(FuzzableRequest(URL("http://w3af.org/not-protected/")))

        self.assertEqual(kb.kb.get("basic_auth", "auth"), [])

    def test_long_description(self):
        self.assertIn("bruteforces basic authentication", basic_auth().get_long_desc())

    def test_audit_skips_already_tested_url(self):
        url = URL("http://w3af.org/admin/")

        # http_auth_detect reported a basic-auth protected directory
        info = Info("HTTP basic auth", "desc for a basic auth endpoint", 1, "x")
        info.set_url(url)
        kb.kb.append("http_auth_detect", "auth", info)

        plugin = basic_auth()
        plugin.set_knowledge_base(kb.kb)
        plugin._already_tested.append(url.get_domain_path())

        # audit() returns without bruteforcing because the URL is in the
        # already-tested list
        plugin.audit(FuzzableRequest(url))

        self.assertEqual(kb.kb.get("basic_auth", "auth"), [])

    def test_end_without_findings_is_a_noop(self):
        plugin = basic_auth()
        plugin.set_knowledge_base(kb.kb)
        plugin.end()

        self.assertEqual(kb.kb.get("basic_auth", "auth"), [])


class TestFailedLoginPage(unittest.TestCase):
    def test_exact_match_on_either_body(self):
        page = FailedLoginPage("body a", "body b")

        self.assertTrue(page.matches("body a"))
        self.assertTrue(page.matches("body b"))

    def test_clearly_different_body_is_not_a_match(self):
        page = FailedLoginPage("a" * 500, "a" * 500)

        self.assertFalse(page.matches("b" * 500))

    def test_short_random_difference_is_treated_as_failed(self):
        # The header/footer are shared so the bodies are fuzzy-equal; the
        # per-page difference is a short random token (as a CSRF token would
        # be), which must be recognized as noise, not a success.
        header = "\n".join(f"<li>menu item {i}</li>" for i in range(100))
        footer = "\n".join(f"<p>footer line {i}</p>" for i in range(100))

        def failed(token):
            return f"{header}\nInvalid username or password {token}\n{footer}"

        page = FailedLoginPage(failed("1034"), failed("7365"))

        self.assertTrue(page.matches(failed("9999")))

    def test_long_real_difference_is_not_a_match(self):
        # A long (>= 64 chars), multi-line success block exercises the
        # chunk-based fuzzy comparison instead of the short-difference path.
        header = "\n".join(f"<li>menu item {i}</li>" for i in range(100))
        footer = "\n".join(f"<p>footer line {i}</p>" for i in range(100))

        def body(message):
            return f"{header}\n{message}\n{footer}"

        failed = "Invalid username or password, please try again later today"
        success = "\n".join(
            f"<a href='/account/{i}'>welcome back, administrator {i}</a>"
            for i in range(10)
        )

        page = FailedLoginPage(body(failed), body(failed))

        self.assertFalse(page.matches(body(success)))
