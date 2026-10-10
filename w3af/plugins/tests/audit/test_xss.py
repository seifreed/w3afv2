"""
test_xss.py

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
from typing import ClassVar
from unittest import TestCase

import pytest

from w3af.core.data.constants import severity
from w3af.core.data.context.context.css import ALL_CONTEXTS as ALL_CSS_CONTEXTS
from w3af.core.data.context.context.html import ALL_CONTEXTS as ALL_HTML_CONTEXTS
from w3af.core.data.context.context.javascript import ALL_CONTEXTS as ALL_JS_CONTEXTS
from w3af.core.data.kb.config import cf
from w3af.plugins.audit.xss import xss
from w3af.plugins.tests.audit.vulnerable_xss import (
    EchoPage,
    GuestBook,
    RedirectWithQuery,
    remove_backticks,
    remove_script_tags,
    strip_quotes,
)
from w3af.plugins.tests.audit.wavsep_xss_site import (
    CASES,
    expected_vulns,
    wavsep_xss_responses,
)
from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest

MOTH_XSS_URL = "http://moth/audit/xss/"
MOTH_XSS_302_URL = "http://moth/w3af/audit/xss/302/"
WAVSEP_XSS_URL = (
    "http://wavsep/wavsep/active/Reflected-XSS/RXSS-Detection-Evaluation-GET/"
)
UPLOAD_ECHO_URL = "http://php-moth/audit/file_upload/echo_content/"

SAFE_CSP = {"Content-Security-Policy": "default-src 'self'"}
WEAK_CSP = {"Content-Security-Policy": "script-src 'self'"}
JSON_HEADERS = {"Content-Type": "application/json"}
NOSNIFF_JSON_HEADERS = {**JSON_HEADERS, "X-Content-Type-Options": "nosniff"}

TEXT_FORM_FIELDS = (
    '<input type="text" name="text" value="hello"/>'
    '<input type="submit" name="Submit" value="Submit"/>'
)


def form(action, method, fields=TEXT_FORM_FIELDS, enctype=None):
    enctype_attr = f' enctype="{enctype}"' if enctype else ""
    return f'<form action="{action}" method="{method}"{enctype_attr}>{fields}</form>'


def page_responses(base_url, file_name, handler, methods=("GET",)):
    url = re.compile(re.escape(base_url + file_name) + r"(\?.*)?$")
    return [MockResponse(url, handler, method=method) for method in methods]


def moth_xss_responses():
    base = MOTH_XSS_URL
    echo_text = EchoPage("$text")
    responses = [
        MockResponse(
            base,
            "<html><body>"
            '<a href="simple_xss.py?text=1">simple</a>'
            '<a href="simple_xss_GET_form.py">get form</a>'
            '<a href="xss_multipart_form.py">multipart form</a>'
            '<a href="script_insensitive_blacklist_xss.py?text=1">blacklist</a>'
            '<a href="script_blacklist_xss.py?text=1">blacklist</a>'
            '<a href="lower_str_xss.py?text=1">lower</a>'
            '<a href="simple_xss_form.py">post form</a>'
            '<a href="two_inputs_form.py">two inputs</a>'
            '<a href="persistent_xss_form.py">persistent</a>'
            '<a href="xss_with_safe_csp.py?text=1">safe csp</a>'
            '<a href="xss_with_weak_csp.py?text=1">weak csp</a>'
            '<a href="499_check.py?text=1">499</a>'
            '<a href="json_xss.py?text=1">json</a>'
            '<a href="json_without_nosniff_xss.py?text=1">json</a>'
            '<a href="backtick_filter_xss.py?text=1">backtick</a>'
            '<a href="persistent_xss_with_csp.py">persistent with csp</a>'
            '<a href="logo.png">logo</a>'
            "</body></html>",
        ),
        *page_responses(base, "simple_xss.py", echo_text),
        *page_responses(
            base,
            "simple_xss_GET_form.py",
            EchoPage(form("simple_xss_GET_form.py", "GET") + "$text"),
        ),
        *page_responses(
            base,
            "xss_multipart_form.py",
            EchoPage(
                form(
                    "xss_multipart_form.py",
                    "POST",
                    '<input type="text" name="text" value="hello"/>'
                    '<input type="submit" value="send"/>',
                    enctype="multipart/form-data",
                )
                + "$text"
            ),
            methods=("GET", "POST"),
        ),
        *page_responses(
            base,
            "script_insensitive_blacklist_xss.py",
            EchoPage("$text", transform=remove_script_tags),
        ),
        *page_responses(
            base,
            "script_blacklist_xss.py",
            EchoPage("$text", transform=remove_script_tags),
        ),
        *page_responses(
            base, "lower_str_xss.py", EchoPage("$text", transform=str.lower)
        ),
        *page_responses(
            base,
            "simple_xss_form.py",
            EchoPage(form("simple_xss_form.py", "POST") + "$text"),
            methods=("GET", "POST"),
        ),
        *page_responses(
            base,
            "two_inputs_form.py",
            EchoPage(
                form(
                    "two_inputs_form.py",
                    "POST",
                    '<input type="text" name="name" value="john"/>'
                    '<input type="text" name="address" value="street"/>'
                    '<input type="submit" name="Submit" value="Submit"/>',
                )
                + "$address"
            ),
            methods=("GET", "POST"),
        ),
        *page_responses(
            base, "persistent_xss_form.py", GuestBook(), methods=("GET", "POST")
        ),
        *page_responses(
            base, "xss_with_safe_csp.py", EchoPage("$text", headers=SAFE_CSP)
        ),
        *page_responses(
            base, "xss_with_weak_csp.py", EchoPage("$text", headers=WEAK_CSP)
        ),
        *page_responses(
            base,
            "499_check.py",
            EchoPage('<input type="text" value="$text">', transform=strip_quotes),
        ),
        *page_responses(
            base,
            "json_xss.py",
            EchoPage('{"text": "$text"}', headers=NOSNIFF_JSON_HEADERS),
        ),
        *page_responses(
            base,
            "json_without_nosniff_xss.py",
            EchoPage('{"text": "$text"}', headers=JSON_HEADERS),
        ),
        *page_responses(
            base,
            "backtick_filter_xss.py",
            EchoPage("$text", transform=remove_backticks),
        ),
        *page_responses(
            base,
            "persistent_xss_with_csp.py",
            GuestBook(headers=SAFE_CSP),
            methods=("GET", "POST"),
        ),
        MockResponse(base + "logo.png", "PNG", content_type="image/png"),
    ]
    return responses


def redirect_responses():
    base = MOTH_XSS_302_URL
    printer = EchoPage("$a $x $added")
    return [
        MockResponse(
            base,
            "<html><body>"
            '<a href="302.php?x=1">x</a>'
            '<a href="302.php?a=1">a</a>'
            '<a href="printer.php?added=1">printer</a>'
            "</body></html>",
        ),
        *page_responses(
            base, "302.php", RedirectWithQuery(base + "printer.php", "$a $x")
        ),
        *page_responses(base, "printer.php", printer),
    ]


def upload_echo_responses():
    return [
        MockResponse(
            UPLOAD_ECHO_URL,
            "<html><body>"
            + form(
                "txt_uploader.php",
                "POST",
                '<input type="file" name="txt_file"/>'
                '<input type="submit" value="Upload"/>',
                enctype="multipart/form-data",
            )
            + "</body></html>",
        ),
        *page_responses(
            UPLOAD_ECHO_URL,
            "txt_uploader.php",
            EchoPage("$txt_file", files_only=True),
            methods=("GET", "POST"),
        ),
    ]


class XssPluginTest(PluginTest):

    SMOKE_PLUGINS: ClassVar[dict] = {
        "audit": (PluginConfig("xss", ("persistent_xss", True, PluginConfig.BOOL)),),
    }
    CRAWL_PLUGINS: ClassVar[dict] = {
        "audit": (PluginConfig("xss", ("persistent_xss", True, PluginConfig.BOOL)),),
        "crawl": (
            PluginConfig("web_spider", ("only_forward", True, PluginConfig.BOOL)),
        ),
    }

    def normalize_kb_data(self, xss_vulns):
        """
        Take the XSS vulns as input and translate them into a list of tuples
        which contain:
            - Vulnerable URL
            - Vulnerable parameter
            - All parameters that were sent
        """
        kb_data = []

        for xss_vuln in xss_vulns:
            mutant = xss_vuln.get_mutant()

            data = (
                str(mutant.get_url()),
                mutant.get_token_name(),
                tuple(sorted(mutant.get_dc().keys())),
            )

            kb_data.append(data)

        return kb_data

    def normalize_expected_data(self, target_url, expected):
        """
        Take a list with the expected vulnerabilities to be found  as input
        and translate them into a list of tuples which contain:
            - Vulnerable URL
            - Vulnerable parameter
            - All parameters that were sent
        """
        return [(target_url + e[0], e[1], tuple(sorted(e[2]))) for e in expected]

    def assert_xss_found(self, target_url, expected, optional=()):
        """
        :param expected: The vulnerabilities which must be found
        :param optional: Vulnerabilities which can be found, depending on the
                         order in which the framework audits the pages
        """
        xss_vulns = self.kb.get("xss", "xss")
        kb_data = set(self.normalize_kb_data(xss_vulns))
        expected_data = set(self.normalize_expected_data(target_url, expected))
        optional_data = set(self.normalize_expected_data(target_url, optional))

        self.assertEqual(set(), expected_data - kb_data)
        self.assertEqual(set(), kb_data - expected_data - optional_data)


class TestXSS(XssPluginTest):

    target_url = MOTH_XSS_URL

    MOCK_RESPONSES: ClassVar[list] = moth_xss_responses()

    @pytest.mark.smoke
    def test_find_one_xss(self):
        """
        Simplest possible test to verify that we identify XSSs.
        """
        self._scan(MOTH_XSS_URL + "simple_xss.py?text=1", self.SMOKE_PLUGINS)

        self.assert_xss_found(MOTH_XSS_URL, [("simple_xss.py", "text", ["text"])])

    def test_no_false_positive_499(self):
        """
        Avoiding false positives in the case where the payload is echoed back
        inside an attribute and the quotes are removed.

        :see: https://github.com/andresriancho/w3af/pull/499
        """
        self._scan(MOTH_XSS_URL + "499_check.py?text=1", self.SMOKE_PLUGINS)

        xss_vulns = self.kb.get("xss", "xss")

        self.assertEqual(0, len(xss_vulns), xss_vulns)

    def test_found_xss(self):
        self._scan(MOTH_XSS_URL, self.CRAWL_PLUGINS)

        expected = [
            # Trivial
            ("simple_xss.py", "text", ["text"]),
            # Form with GET method
            # https://github.com/andresriancho/w3af/issues/3149
            ("simple_xss_GET_form.py", "text", ["Submit", "text"]),
            # Form with multipart enctype
            # https://github.com/andresriancho/w3af/issues/3149
            ("xss_multipart_form.py", "text", ["text"]),
            # Simple filters
            ("script_insensitive_blacklist_xss.py", "text", ["text"]),
            ("script_blacklist_xss.py", "text", ["text"]),
            # Simple encodings
            ("lower_str_xss.py", "text", ["text"]),
            # Forms with POST
            ("simple_xss_form.py", "text", ["Submit", "text"]),
            ("two_inputs_form.py", "address", ["Submit", "address", "name"]),
            # Persistent XSS
            ("persistent_xss_form.py", "text", ["Submit", "text"]),
            # XSS with CSP
            ("xss_with_safe_csp.py", "text", ["text"]),
            ("xss_with_weak_csp.py", "text", ["text"]),
            # The filter removes one char, so only the individual payloads work
            ("backtick_filter_xss.py", "text", ["text"]),
            # Persistent XSS in a page with CSP
            ("persistent_xss_with_csp.py", "text", ["Submit", "text"]),
        ]
        self.assert_xss_found(MOTH_XSS_URL, expected)

        # Now we want to verify that the vulnerability with safe CSP has lower
        # severity than the one with weak CSP
        xss_vulns = self.kb.get("xss", "xss")
        csp_vulns = [v for v in xss_vulns if "/xss_with_" in v.get_url()]
        self.assertEqual(len(csp_vulns), 2)

        severities = [v.get_severity() for v in csp_vulns]
        self.assertEqual(set(severities), {severity.MEDIUM, severity.LOW}, csp_vulns)

    def test_persistent_xss_is_flagged_as_persistent(self):
        self._scan(MOTH_XSS_URL + "persistent_xss_form.py", self.CRAWL_PLUGINS)

        persistent = [
            v for v in self.kb.get("xss", "xss") if v.get("persistent", False)
        ]
        self.assertEqual(1, len(persistent))
        self.assertEqual(
            "Persistent Cross-Site Scripting vulnerability", persistent[0].get_name()
        )

    def test_persistent_xss_with_csp_has_lower_severity(self):
        self._scan(MOTH_XSS_URL + "persistent_xss_with_csp.py", self.CRAWL_PLUGINS)

        vulns = self.kb.get("xss", "xss")
        self.assertEqual(1, len(vulns))
        self.assertEqual(severity.MEDIUM, vulns[0].get_severity())

    def test_json_responses_are_not_xss(self):
        for page in ("json_xss.py", "json_without_nosniff_xss.py"):
            self._scan(f"{MOTH_XSS_URL}{page}?text=1", self.CRAWL_PLUGINS)

            self.assertEqual([], self.kb.get("xss", "xss"))

    def test_persistent_xss_disabled_only_reports_reflected(self):
        plugins = {
            "audit": (
                PluginConfig("xss", ("persistent_xss", False, PluginConfig.BOOL)),
            ),
            "crawl": self.CRAWL_PLUGINS["crawl"],
        }
        self._scan(MOTH_XSS_URL + "persistent_xss_form.py", plugins)

        self.assertEqual([], self.kb.get("xss", "xss"))


class TestXSSRedirect(XssPluginTest):

    target_url = MOTH_XSS_302_URL

    MOCK_RESPONSES: ClassVar[list] = redirect_responses()

    def test_found_xss_with_redirect(self):
        self._scan(MOTH_XSS_302_URL, self.CRAWL_PLUGINS)

        expected = [
            ("302.php", "x", ("x",)),
            ("302.php", "a", ("a",)),
            ("printer.php", "a", ("a", "added")),
            ("printer.php", "added", ("added",)),
            ("printer.php", "x", ("x", "added")),
        ]
        # The framework reports a vulnerable parameter of a page only once, so
        # which of the "added" combinations is reported depends on the order
        # in which the redirect targets are audited.
        optional = [
            ("printer.php", "added", ("a", "added")),
            ("printer.php", "added", ("x", "added")),
        ]
        self.assert_xss_found(MOTH_XSS_302_URL, expected, optional)


class TestXSSWavsep(XssPluginTest):

    target_url = WAVSEP_XSS_URL

    MOCK_RESPONSES: ClassVar[list] = wavsep_xss_responses(WAVSEP_XSS_URL)

    def test_2919_javascript_src_frame(self):
        """
        https://github.com/andresriancho/w3af/issues/2919
        https://github.com/andresriancho/w3af/issues/1557
        """
        target = WAVSEP_XSS_URL + "Case16-Js2ScriptSupportingProperty.jsp?userinput=1"
        self._scan(target, self.SMOKE_PLUGINS)

        expected = [
            ("Case16-Js2ScriptSupportingProperty.jsp", "userinput", ["userinput"])
        ]
        self.assert_xss_found(WAVSEP_XSS_URL, expected)

    def test_found_wavsep_get_xss(self):
        self._scan(WAVSEP_XSS_URL, self.CRAWL_PLUGINS)

        expected = [vuln for case in CASES for vuln in expected_vulns(case)]
        self.assert_xss_found(WAVSEP_XSS_URL, expected)


class TestXSSFileUpload(XssPluginTest):

    target_url = UPLOAD_ECHO_URL

    MOCK_RESPONSES: ClassVar[list] = upload_echo_responses()

    def scan_file_upload_fuzz_files(self):
        self._scan(UPLOAD_ECHO_URL, self.CRAWL_PLUGINS)

    def test_user_configured_find_in_file_upload_content(self):
        """
        Do not send file content mutants unless the user configures it.
        https://github.com/andresriancho/w3af/issues/3149
        """
        # Set the value to False (True is the default)
        cf.save("fuzz_form_files", False)

        try:
            self.scan_file_upload_fuzz_files()
        finally:
            # Restore the default
            cf.save("fuzz_form_files", True)

        xss_vulns = self.kb.get("xss", "xss")
        self.assertEqual(len(xss_vulns), 0, xss_vulns)

    def test_find_in_file_upload_content(self):
        """
        Find XSS in the content of an uploaded file
        https://github.com/andresriancho/w3af/issues/3149
        """
        self.scan_file_upload_fuzz_files()

        self.assert_xss_found(
            UPLOAD_ECHO_URL, [("txt_uploader.php", "txt_file", ["txt_file"])]
        )


class TestXSSPluginDescription(TestCase):
    def test_long_description_names_the_option(self):
        self.assertIn("persistent_xss", xss().get_long_desc())


class TestXSSPayloadsBreak(TestCase):
    def test_xss_plugin_can_break_html(self):
        for context_klass in ALL_HTML_CONTEXTS:

            payload_broke_context = False

            for payload in xss.PAYLOADS:

                try:
                    # Most contexts
                    context = context_klass(payload, "")
                except TypeError:
                    # Attribute contexts
                    context = context_klass(payload, "", "")

                if context.can_break():
                    payload_broke_context = True
                    break

            if not payload_broke_context:
                klass_name = context.__class__.__name__
                self.assertTrue(False, f"No XSS payload breaks {klass_name}")

    def test_xss_plugin_can_break_js(self):
        for context_klass in ALL_JS_CONTEXTS:

            payload_broke_context = False

            for payload in xss.PAYLOADS:

                context = context_klass(payload, "")

                if context.is_executable():
                    payload_broke_context = True
                    break

                if context.can_break():
                    payload_broke_context = True
                    break

            if not payload_broke_context:
                klass_name = context.__class__.__name__
                self.assertTrue(False, f"No XSS payload breaks {klass_name}")

    def test_xss_plugin_can_break_css(self):
        for context_klass in ALL_CSS_CONTEXTS:

            payload_broke_context = False

            for payload in xss.PAYLOADS:

                context = context_klass(payload, "")

                if context.is_executable():
                    payload_broke_context = True
                    break

                if context.can_break():
                    payload_broke_context = True
                    break

            if not payload_broke_context:
                klass_name = context.__class__.__name__
                self.assertTrue(False, f"No XSS payload breaks {klass_name}")
