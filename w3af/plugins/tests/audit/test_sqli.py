"""
test_sqli.py

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

import pytest

from w3af.plugins.audit.sqli import sqli
from w3af.plugins.tests.audit.vulnerable_responses import html_page, request_param
from w3af.plugins.tests.audit.vulnerable_sql import ErrorMode, SqlQueryPage
from w3af.plugins.tests.audit.wavsep_sql_site import (
    DETECTION_CASES,
    EXPERIMENTAL_CASES,
    SuiteSite,
    identical_suite_site,
    suite_site,
)
from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest

MOTH_SQLI_URL = "http://moth/audit/sql_injection/"
SQLMAP_BASE_PATH = "/sqlmap/mysql/"
SQLMAP_URL = f"http://sqlmap-testenv{SQLMAP_BASE_PATH}"
WAVSEP_HOST = "http://wavsep"
WAVSEP_SQLI_PATH = "/wavsep/active/SQL-Injection/SInjection-Detection-Evaluation-"

SELECT_BY_ID = "SELECT * FROM records WHERE id = {id}"

SQLMAP_ERROR_PAGES = {
    "get_int.php": "SELECT * FROM records WHERE id = {id}",
    "get_int_inline.php": "SELECT (SELECT name FROM records WHERE id = {id})",
    "get_int_rand.php": "SELECT * FROM records WHERE id = {id} OR id = 0",
    "get_int_user.php": "SELECT * FROM records WHERE id = {id} AND name != 'nobody'",
    "get_int_blob.php": "SELECT * FROM records WHERE id = {id} AND msg != ''",
    "get_int_filtered.php": "SELECT * FROM records WHERE id = {id} AND 1 = 1",
    "get_int_nolimit.php": "SELECT * FROM records WHERE id = {id} ORDER BY id",
    "get_int_limit.php": "SELECT * FROM records LIMIT {id}",
    "get_int_limit_second.php": "SELECT * FROM records LIMIT 1, {id}",
    "get_int_orderby.php": "SELECT * FROM records ORDER BY {id}",
    "get_int_groupby.php": "SELECT * FROM records GROUP BY {id}",
    "get_int_having.php": "SELECT id FROM records GROUP BY id HAVING id = {id}",
    "get_brackets.php": "SELECT * FROM records WHERE id = ({id})",
    "get_str.php": "SELECT * FROM records WHERE name = '{id}'",
    "get_str_union.php": "SELECT * FROM records WHERE name = '{id}'",
    "get_str_brackets.php": "SELECT * FROM records WHERE (name = '{id}')",
    "get_dstr.php": 'SELECT * FROM records WHERE name = "{id}"',
    "get_str_like.php": "SELECT * FROM records WHERE name LIKE '%{id}%'",
    "get_str_like_par.php": "SELECT * FROM records WHERE (name LIKE '%{id}%')",
    "get_str_like_par2.php": "SELECT * FROM records WHERE ((name LIKE '%{id}%'))",
    "get_str_like_par3.php": "SELECT * FROM records WHERE (((name LIKE '%{id}%')))",
    "get_dstr_like_par.php": 'SELECT * FROM records WHERE (name LIKE "%{id}%")',
    "get_dstr_like_par2.php": 'SELECT * FROM records WHERE ((name LIKE "%{id}%"))',
}

SQLMAP_HIDDEN_ERROR_PAGES = {
    "get_int_noerror.php": ErrorMode.DEFAULT_PAGE,
    "get_int_nooutput.php": ErrorMode.IDENTICAL_PAGE,
}

CRAWL_CONFIG = (
    PluginConfig(
        "web_spider",
        ("only_forward", True, PluginConfig.BOOL),
        ("ignore_regex", ".*(asp|aspx)", PluginConfig.STR),
    ),
)


def sqlmap_index():
    pages = [*SQLMAP_ERROR_PAGES, *SQLMAP_HIDDEN_ERROR_PAGES]
    links = "".join(f'<li><a href="{page}?id=1">{page}</a></li>' for page in pages)
    return f"<html><body><ul>{links}</ul></body></html>"


def sqlmap_responses():
    responses = [MockResponse(SQLMAP_URL, sqlmap_index())]

    for page, query in SQLMAP_ERROR_PAGES.items():
        responses.append(
            MockResponse(
                re.compile(re.escape(SQLMAP_URL + page) + r"(\?.*)?$"),
                SqlQueryPage(query),
            )
        )

    for page, error_mode in SQLMAP_HIDDEN_ERROR_PAGES.items():
        responses.append(
            MockResponse(
                re.compile(re.escape(SQLMAP_URL + page) + r"(\?.*)?$"),
                SqlQueryPage(SELECT_BY_ID, error_mode),
            )
        )

    return responses


@pytest.mark.smoke
class TestSQLI(PluginTest):

    target_url = f"{MOTH_SQLI_URL}where_integer_qs.py"

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(
            re.compile(re.escape(target_url) + r"(\?.*)?$"),
            SqlQueryPage(SELECT_BY_ID),
        )
    ]

    _run_configs: ClassVar[dict] = {
        "cfg": {
            "target": target_url + "?id=1",
            "plugins": {
                "audit": (PluginConfig("sqli"),),
            },
        }
    }

    def test_found_sqli(self):
        cfg = self._run_configs["cfg"]
        self._scan(cfg["target"], cfg["plugins"])
        vulns = self.kb.get("sqli", "sqli")

        self.assertEqual(1, len(vulns))

        # Now some tests around specific details of the found vuln
        vuln = vulns[0]
        self.assertEqual("syntax error", vuln["error"])
        self.assertEqual("Unknown database", vuln["db"])
        self.assertEqual(self.target_url, str(vuln.get_url()))


ERRORS_URL = "http://moth/audit/sql_errors/"
ORACLE_ERROR = "ORA-00933: SQL command not properly ended"
STATIC_ERROR = "syntax error in the query, as always"


def oracle_error_page(mock_response, request, uri, response_headers):
    if "'" in request_param(request, "id"):
        return html_page(response_headers, f"Database failure: {ORACLE_ERROR}")
    return html_page(response_headers, "Everything is fine")


def static_error_page(mock_response, request, uri, response_headers):
    return html_page(response_headers, STATIC_ERROR)


class TestSQLIErrorDetection(PluginTest):

    target_url = ERRORS_URL

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(
            re.compile(re.escape(ERRORS_URL) + r"oracle\.py.*"), oracle_error_page
        ),
        MockResponse(
            re.compile(re.escape(ERRORS_URL) + r"static\.py.*"), static_error_page
        ),
    ]

    plugins: ClassVar[dict] = {"audit": (PluginConfig("sqli"),)}

    def test_error_matched_by_regular_expression_names_the_database(self):
        self._scan(ERRORS_URL + "oracle.py?id=1", self.plugins)

        vulns = self.kb.get("sqli", "sqli")
        self.assertEqual(1, len(vulns))
        self.assertEqual("ORA-0093", vulns[0]["error"])
        self.assertEqual("Oracle database", vulns[0]["db"])

    def test_error_already_in_the_original_response_is_not_a_vulnerability(self):
        self._scan(ERRORS_URL + "static.py?id=1", self.plugins)

        self.assertEqual([], self.kb.get("sqli", "sqli"))

    def test_long_description_names_the_payload(self):
        self.assertIn("d'z\"0", sqli().get_long_desc())


class TestSQLMapTestEnv(PluginTest):

    base_path = SQLMAP_BASE_PATH
    target_url = SQLMAP_URL

    MOCK_RESPONSES: ClassVar[list] = sqlmap_responses()

    config: ClassVar[dict] = {
        "audit": (PluginConfig("sqli"),),
        "crawl": CRAWL_CONFIG,
    }

    def test_found_sqli_in_testenv(self):
        """
        Every page which shows the database error is found, the ones that hide
        the error from the response are not reported by the sqli plugin.
        """
        expected_path_param = {(page, "id") for page in SQLMAP_ERROR_PAGES}
        ok_to_miss = set(SQLMAP_HIDDEN_ERROR_PAGES)
        kb_addresses = {("sqli", "sqli")}

        self._scan_assert(
            self.config, expected_path_param, ok_to_miss, kb_addresses, set()
        )


class WAVSEPTest(PluginTest):
    site: ClassVar[SuiteSite]
    config: ClassVar[dict] = {
        "audit": (PluginConfig("sqli"), PluginConfig("blind_sqli")),
        "crawl": CRAWL_CONFIG,
    }

    def assert_suite_detected(self):
        """
        Every vulnerable parameter of the suite is found, and nothing else
        is reported.
        """
        self._scan_assert(
            self.config,
            self.site.expected_vulns,
            set(),
            {("sqli", "sqli"), ("blind_sqli", "blind_sqli")},
            {"index.jsp"},
        )


def wavsep_path(suite_name):
    return f"{WAVSEP_SQLI_PATH}{suite_name}/"


class TestWAVSEPError(WAVSEPTest):

    base_path = wavsep_path("GET-200Error")
    target_url = WAVSEP_HOST + base_path
    site = suite_site(
        target_url, DETECTION_CASES, "With200Errors", ErrorMode.SHOW_200, False
    )
    MOCK_RESPONSES: ClassVar[list] = site.responses()

    def test_found_sqli_wavsep_error(self):
        self.assert_suite_detected()


class TestWAVSEP500Error(WAVSEPTest):

    base_path = wavsep_path("GET-500Error")
    target_url = WAVSEP_HOST + base_path
    site = suite_site(
        target_url, DETECTION_CASES, "WithErrors", ErrorMode.SHOW_500, False
    )
    MOCK_RESPONSES: ClassVar[list] = site.responses()

    def test_found_sqli_wavsep_error(self):
        self.assert_suite_detected()


class TestWAVSEPWithDifferentiation(WAVSEPTest):

    base_path = wavsep_path("GET-200Valid")
    target_url = WAVSEP_HOST + base_path
    site = suite_site(
        target_url,
        DETECTION_CASES,
        "WithDifferent200Responses",
        ErrorMode.DEFAULT_PAGE,
        False,
    )
    MOCK_RESPONSES: ClassVar[list] = site.responses()

    def test_found_sqli_wavsep_differentiation(self):
        self.assert_suite_detected()


class TestWAVSEPIdentical(WAVSEPTest):

    base_path = wavsep_path("GET-200Identical")
    target_url = WAVSEP_HOST + base_path
    site = identical_suite_site(target_url, False)
    MOCK_RESPONSES: ClassVar[list] = site.responses()

    def test_found_sqli_wavsep_identical(self):
        self.assert_suite_detected()


class TestWAVSEPExperimental(WAVSEPTest):

    base_path = wavsep_path("GET-200Error-Experimental")
    target_url = WAVSEP_HOST + base_path
    site = suite_site(
        target_url, EXPERIMENTAL_CASES, "With200Errors", ErrorMode.SHOW_200, False
    )
    MOCK_RESPONSES: ClassVar[list] = site.responses()

    def test_found_sqli_wavsep_experimental(self):
        self.assert_suite_detected()


class TestWAVSEPError500POST(WAVSEPTest):

    base_path = wavsep_path("POST-500Error")
    target_url = WAVSEP_HOST + base_path
    site = suite_site(
        target_url, DETECTION_CASES, "WithErrors", ErrorMode.SHOW_500, True
    )
    MOCK_RESPONSES: ClassVar[list] = site.responses()

    def test_found_sqli_wavsep_error_500_post(self):
        self.assert_suite_detected()


class TestWAVSEPError200POST(WAVSEPTest):

    base_path = wavsep_path("POST-200Error")
    target_url = WAVSEP_HOST + base_path
    site = suite_site(
        target_url, DETECTION_CASES, "With200Errors", ErrorMode.SHOW_200, True
    )
    MOCK_RESPONSES: ClassVar[list] = site.responses()

    def test_found_sqli_wavsep_error_200_post(self):
        self.assert_suite_detected()


class TestWAVSEPWithDifferentiationPOST(WAVSEPTest):

    base_path = wavsep_path("POST-200Valid")
    target_url = WAVSEP_HOST + base_path
    site = suite_site(
        target_url,
        DETECTION_CASES,
        "WithDifferent200Responses",
        ErrorMode.DEFAULT_PAGE,
        True,
    )
    MOCK_RESPONSES: ClassVar[list] = site.responses()

    def test_found_sqli_wavsep_differentiation_post(self):
        self.assert_suite_detected()


class TestWAVSEPIdenticalPOST(WAVSEPTest):

    base_path = wavsep_path("POST-200Identical")
    target_url = WAVSEP_HOST + base_path
    site = identical_suite_site(target_url, True)
    MOCK_RESPONSES: ClassVar[list] = site.responses()

    def test_found_sqli_wavsep_identical_post(self):
        self.assert_suite_detected()


class TestWAVSEPExperimentalPOST(WAVSEPTest):

    base_path = wavsep_path("POST-200Error-Experimental")
    target_url = WAVSEP_HOST + base_path
    site = suite_site(
        target_url, EXPERIMENTAL_CASES, "With200Errors", ErrorMode.SHOW_200, True
    )
    MOCK_RESPONSES: ClassVar[list] = site.responses()

    def test_found_sqli_wavsep_experimental_post(self):
        self.assert_suite_detected()
