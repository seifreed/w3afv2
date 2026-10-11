"""
test_blind_sqli.py

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
import unittest
from typing import ClassVar

from w3af.core.data.constants import severity
from w3af.core.data.fuzzer.fuzzer import create_mutants
from w3af.core.data.kb.vuln import Vuln
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.request.fuzzable_request import FuzzableRequest
from w3af.plugins.audit.blind_sqli import blind_sqli
from w3af.plugins.tests.audit.noisy_responses import (
    NoisyPage,
    RandomDelayPage,
    RandomLinesPage,
)
from w3af.plugins.tests.audit.vulnerable_sql import (
    ErrorMode,
    FormOrQuery,
    SqlQueryPage,
)
from w3af.plugins.tests.audit.wavsep_xss_site import wavsep_xss_responses
from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest

CONFIG = {
    "audit": (PluginConfig("blind_sqli"),),
    "crawl": (PluginConfig("web_spider", ("only_forward", True, PluginConfig.BOOL)),),
}

MOTH_BLIND_URL = "http://moth/audit/blind_sqli/"
OLD_MOTH_BASE_PATH = "/w3af/audit/blind_sql_injection/"
OLD_MOTH_URL = f"http://old-moth{OLD_MOTH_BASE_PATH}"
WAVSEP_XSS_URL = (
    "http://wavsep/wavsep/active/Reflected-XSS/RXSS-Detection-Evaluation-GET/"
)

BY_ID = "SELECT * FROM records WHERE id = {id}"
BY_NAME = "SELECT * FROM records WHERE name = '{uname}'"


def page_response(base_url, file_name, page, method="GET"):
    url = re.compile(re.escape(base_url + file_name) + r"(\?.*)?$")
    return MockResponse(url, page, method=method)


def hidden_error_page(query):
    """
    A page which hides the database errors: true and false conditions are the
    only difference in the response.
    """
    return SqlQueryPage(query, ErrorMode.DEFAULT_PAGE)


def form_html(action, method, field):
    return (
        f'<form action="{action}" method="{method}">'
        f'<input type="text" name="{field}" value="1"/>'
        '<input type="submit" value="send"/></form>'
    )


def moth_blind_responses():
    return [
        page_response(MOTH_BLIND_URL, "where_integer_qs.py", hidden_error_page(BY_ID)),
        page_response(
            MOTH_BLIND_URL, "where_string_single_qs.py", hidden_error_page(BY_NAME)
        ),
        page_response(
            MOTH_BLIND_URL,
            "blind_where_integer_form.py",
            FormOrQuery(
                form_html("blind_where_integer_form.py", "POST", "text"),
                "text",
                hidden_error_page("SELECT * FROM records WHERE id = {text}"),
            ),
            method="GET",
        ),
        page_response(
            MOTH_BLIND_URL,
            "blind_where_integer_form.py",
            FormOrQuery(
                form_html("blind_where_integer_form.py", "POST", "text"),
                "text",
                hidden_error_page("SELECT * FROM records WHERE id = {text}"),
            ),
            method="POST",
        ),
        page_response(
            MOTH_BLIND_URL,
            "blind_where_integer_form_get.py",
            FormOrQuery(
                form_html("blind_where_integer_form_get.py", "GET", "q"),
                "q",
                hidden_error_page("SELECT * FROM records WHERE id = {q}"),
            ),
        ),
    ]


class TestDjangoBlindSQLI(PluginTest):

    target_url = MOTH_BLIND_URL
    MOCK_RESPONSES: ClassVar[list] = moth_blind_responses()

    def test_integer(self):
        target_url = MOTH_BLIND_URL + "where_integer_qs.py"
        self._scan(target_url + "?id=1", CONFIG)

        vulns = self.kb.get("blind_sqli", "blind_sqli")
        self.assertEqual(1, len(vulns))

        # Now some tests around specific details of the found vuln
        vuln = vulns[0]
        self.assertEqual("Blind SQL injection vulnerability", vuln.get_name())
        self.assertFalse("time delays" in vuln.get_desc())
        self.assertEqual("numeric", vuln["type"])
        self.assertEqual(target_url, str(vuln.get_url()))

    def test_single_quote(self):
        target_url = MOTH_BLIND_URL + "where_string_single_qs.py"
        self._scan_single_quote(target_url, "?uname=pablo")

    def test_single_quote_non_true_value_as_init(self):
        target_url = MOTH_BLIND_URL + "where_string_single_qs.py"
        self._scan_single_quote(target_url, "?uname=foobar39")

    def _scan_single_quote(self, target_url, qs):
        self._scan(target_url + qs, CONFIG)

        vulns = self.kb.get("blind_sqli", "blind_sqli")
        self.assertEqual(1, len(vulns))

        # Now some tests around specific details of the found vuln
        vuln = vulns[0]
        self.assertEqual("Blind SQL injection vulnerability", vuln.get_name())
        self.assertFalse("time delays" in vuln.get_desc())
        self.assertEqual("string_single", vuln["type"])
        self.assertEqual(target_url, str(vuln.get_url()))

    def test_found_exploit_blind_sqli_form(self):
        # Run the scan
        target = MOTH_BLIND_URL + "blind_where_integer_form.py"
        self._scan(target, CONFIG)

        # Assert the general results
        vulns = self.kb.get("blind_sqli", "blind_sqli")

        self.assertEqual(1, len(vulns))
        vuln = vulns[0]

        self.assertEqual("Blind SQL injection vulnerability", vuln.get_name())
        self.assertEqual("text", vuln.get_mutant().get_token_name())
        self.assertEqual("blind_where_integer_form.py", vuln.get_url().get_file_name())

    def test_found_exploit_blind_sqli_form_GET(self):
        # Run the scan
        target = MOTH_BLIND_URL + "blind_where_integer_form_get.py"
        self._scan(target, CONFIG)

        # Assert the general results
        vulns = self.kb.get("blind_sqli", "blind_sqli")

        self.assertEqual(1, len(vulns))
        vuln = vulns[0]

        self.assertEqual("Blind SQL injection vulnerability", vuln.get_name())
        self.assertEqual("q", vuln.get_mutant().get_token_name())
        self.assertEqual(
            "blind_where_integer_form_get.py", vuln.get_url().get_file_name()
        )


class TestReflectedXSSFalsePositive(PluginTest):

    target_url = WAVSEP_XSS_URL
    MOCK_RESPONSES: ClassVar[list] = wavsep_xss_responses(WAVSEP_XSS_URL)

    def test_xss_false_positive_1516(self):
        self._scan(WAVSEP_XSS_URL + "Case24-Js2ScriptTag.jsp?userinput=1234", CONFIG)

        vulns = self.kb.get("blind_sqli", "blind_sqli")
        self.assertEqual(0, len(vulns))


def old_moth_responses():
    base = OLD_MOTH_URL
    return [
        MockResponse(
            base,
            "<html><body>"
            '<a href="bsqli_string.php?email=pablo">string</a>'
            '<a href="bsqli_integer.php?id=1">integer</a>'
            '<a href="forms/">forms</a>'
            '<a href="completely_bsqli_single.php?email=pablo">single</a>'
            '<a href="completely_bsqli_double.php?email=pablo">double</a>'
            '<a href="completely_bsqli_integer.php?id=1">integer</a>'
            '<a href="bsqli_string_rnd.php?email=pablo">random</a>'
            '<a href="random_500_lines.php?id=1">random</a>'
            '<a href="random_500_lines_static.php?id=1">random</a>'
            '<a href="random_50_lines.php?id=1">random</a>'
            '<a href="random_50_lines_static.php?id=1">random</a>'
            '<a href="random_5_lines.php?id=1">random</a>'
            '<a href="random_5_lines_static.php?id=1">random</a>'
            '<a href="delay_random.php?id=1">delay</a>'
            "</body></html>",
        ),
        MockResponse(
            base + "forms/",
            '<html><body><a href="test_forms.html">forms</a></body></html>',
        ),
        MockResponse(
            base + "forms/test_forms.html",
            "<html><body>"
            + form_html("data_receptor.php", "POST", "user")
            + "</body></html>",
        ),
        page_response(
            base + "forms/",
            "data_receptor.php",
            hidden_error_page("SELECT * FROM records WHERE name = '{user}'"),
            method="POST",
        ),
        page_response(
            base,
            "bsqli_string.php",
            hidden_error_page("SELECT * FROM records WHERE name = '{email}'"),
        ),
        page_response(base, "bsqli_integer.php", hidden_error_page(BY_ID)),
        page_response(
            base,
            "completely_bsqli_single.php",
            hidden_error_page("SELECT * FROM records WHERE name = '{email}'"),
        ),
        page_response(
            base,
            "completely_bsqli_double.php",
            hidden_error_page('SELECT * FROM records WHERE name = "{email}"'),
        ),
        page_response(base, "completely_bsqli_integer.php", hidden_error_page(BY_ID)),
        page_response(
            base,
            "bsqli_string_rnd.php",
            NoisyPage(
                hidden_error_page("SELECT * FROM records WHERE name = '{email}'")
            ),
        ),
        page_response(base, "random_500_lines.php", RandomLinesPage(500)),
        page_response(base, "random_500_lines_static.php", RandomLinesPage(500, True)),
        page_response(base, "random_50_lines.php", RandomLinesPage(50)),
        page_response(base, "random_50_lines_static.php", RandomLinesPage(50, True)),
        page_response(base, "random_5_lines.php", RandomLinesPage(5)),
        page_response(base, "random_5_lines_static.php", RandomLinesPage(5, True)),
        page_response(base, "delay_random.php", RandomDelayPage()),
    ]


class TestOldMothBlindSQLI(PluginTest):

    base_path = OLD_MOTH_BASE_PATH
    target_url = OLD_MOTH_URL

    MOCK_RESPONSES: ClassVar[list] = old_moth_responses()

    config: ClassVar[dict] = {
        "audit": (PluginConfig("blind_sqli"),),
        "crawl": (
            PluginConfig(
                "web_spider",
                ("only_forward", True, PluginConfig.BOOL),
                ("ignore_regex", ".*(asp|aspx)", PluginConfig.STR),
            ),
        ),
    }

    def test_found_blind_sqli_old_moth(self):
        expected_path_param = {
            ("bsqli_string.php", "email"),
            ("bsqli_integer.php", "id"),
            ("forms/data_receptor.php", "user"),
            ("completely_bsqli_single.php", "email"),
            ("bsqli_string_rnd.php", "email"),
            ("completely_bsqli_double.php", "email"),
            ("completely_bsqli_integer.php", "id"),
        }

        ok_to_miss = {
            # Just the HTML to have a form
            "forms/",
            "forms/test_forms.html",
            # False positive tests, these must NOT be detected by blind_sqli
            "random_500_lines.php",
            "random_500_lines_static.php",
            "random_50_lines.php",
            "random_50_lines_static.php",
            "random_5_lines.php",
            "random_5_lines_static.php",
            "delay_random.php",
        }
        skip_startwith: set[str] = set()
        kb_addresses = {("blind_sqli", "blind_sqli")}

        self._scan_assert(
            self.config, expected_path_param, ok_to_miss, kb_addresses, skip_startwith
        )


TIME_DELAY_URL = "http://moth/audit/blind_sqli_time_delay/"
SHOWN_ERROR_URL = "http://moth/audit/sql_injection/"


class TestBlindSQLITimeDelay(PluginTest):
    """
    The page never changes, only the time it takes to answer does.
    """

    target_url = TIME_DELAY_URL

    MOCK_RESPONSES: ClassVar[list] = [
        page_response(
            TIME_DELAY_URL,
            "identical_page.py",
            SqlQueryPage(BY_ID, ErrorMode.IDENTICAL_PAGE),
        )
    ]

    def test_found_with_time_delays(self):
        self._scan(TIME_DELAY_URL + "identical_page.py?id=1", CONFIG)

        vulns = self.kb.get("blind_sqli", "blind_sqli")
        self.assertEqual(1, len(vulns))

        vuln = vulns[0]
        self.assertEqual("Blind SQL injection vulnerability", vuln.get_name())
        self.assertIn("time delays", vuln.get_desc())
        self.assertEqual("id", vuln.get_token_name())


class TestBlindSQLIWithSQLI(PluginTest):
    """
    The SQL injection is reported once, by the plugin that found it first.
    """

    target_url = SHOWN_ERROR_URL

    MOCK_RESPONSES: ClassVar[list] = [
        page_response(SHOWN_ERROR_URL, "shown_error.py", SqlQueryPage(BY_ID))
    ]

    def test_blind_sqli_does_not_repeat_the_sqli_vulnerability(self):
        plugins = {
            "audit": (PluginConfig("sqli"), PluginConfig("blind_sqli")),
            "crawl": CONFIG["crawl"],
        }
        self._scan(SHOWN_ERROR_URL + "shown_error.py?id=1", plugins)

        self.assertEqual(1, len(self.kb.get("sqli", "sqli")))
        self.assertEqual([], self.kb.get("blind_sqli", "blind_sqli"))


class TestBlindSQLIKnownVulnerabilities(PluginTest):
    """
    The vulnerabilities already in the KB are not searched and reported again.
    """

    target_url = SHOWN_ERROR_URL

    MOCK_RESPONSES: ClassVar[list] = [
        page_response(SHOWN_ERROR_URL, "known.py", hidden_error_page(BY_ID))
    ]

    def known_vulnerability(self, plugin_name, kb_name):
        url = f"{SHOWN_ERROR_URL}known.py?id=1"
        mutant = create_mutants(FuzzableRequest(URL(url)), [""])[0]
        vuln = Vuln.from_mutant(
            "Known vulnerability",
            "This vulnerability was found by a previous plugin",
            severity.HIGH,
            1,
            plugin_name,
            mutant,
        )
        self.kb.append(plugin_name, kb_name, vuln)

    def test_parameter_with_a_sql_injection_is_not_tested(self):
        self.known_vulnerability("sqli", "sqli")

        self._scan(f"{SHOWN_ERROR_URL}known.py?id=1", CONFIG)

        self.assertEqual([], self.kb.get("blind_sqli", "blind_sqli"))

    def test_parameter_with_a_blind_sql_injection_is_not_tested_again(self):
        self.known_vulnerability("blind_sqli", "blind_sqli")

        self._scan(f"{SHOWN_ERROR_URL}known.py?id=1", CONFIG)

        self.assertEqual(1, len(self.kb.get("blind_sqli", "blind_sqli")))
        self.assertEqual(
            "Known vulnerability",
            self.kb.get("blind_sqli", "blind_sqli")[0].get_name(),
        )


class TestBlindSQLIOptions(unittest.TestCase):
    def test_eq_limit_is_read_back(self):
        plugin = blind_sqli()
        options = plugin.get_options()
        options["eq_limit"].set_value(0.5)

        plugin.set_options(options)

        self.assertEqual(0.5, plugin.get_options()["eq_limit"].get_value())

    def test_long_description_names_the_option(self):
        self.assertIn("eq_limit", blind_sqli().get_long_desc())
