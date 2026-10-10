import unittest

from w3af.core.controllers.sql_tools.blind_sqli_response_diff import (
    BlindSqliResponseDiff,
)
from w3af.core.controllers.sql_tools.tests.blind_sqli_sites import (
    ScriptedPages,
    mutant_for,
    parameterized_users,
    static_page,
    users_page,
    vulnerable_users,
)
from w3af.core.data.constants import severity
from w3af.core.data.url.extended_urllib import ExtendedUrllib
from w3af.core.data.url.tests.helpers.route_server import Response, RouteServer

NUMERIC_WHERE = "id = %s"
STRING_WHERE = "name = '%s'"
BIG_FOOTER = "".join(f"<p>paragraph {i}</p>" for i in range(300))
SYNTAX_ERROR = BlindSqliResponseDiff.SYNTAX_ERROR

MANY_USERS = users_page([f"user{i}" for i in range(10)])
NO_USERS = users_page([])
ERROR_PAGE = "<html><body>Database error</body></html>"
HUGE_LISTING = users_page([f"user{i}" for i in range(200)])


class BlindSqliTestCase(unittest.TestCase):
    def setUp(self):
        self.uri_opener = ExtendedUrllib()
        self.addCleanup(self.uri_opener.end)
        self.addCleanup(self.uri_opener.settings.set_default_values)
        self.detector = BlindSqliResponseDiff(self.uri_opener)
        self.detector.set_debugging_id(42)

    def serve(self, routes):
        return RouteServer.serve_for(self, routes)

    def detect(self, server, path, statement_type, query="id=1"):
        mutant = mutant_for(server, path, query)
        return self.detector.is_injectable(mutant, statement_type)


class TestDetectsInjection(BlindSqliTestCase):
    def test_numeric_injection_in_sql_database(self):
        server = self.serve({"/users": vulnerable_users(NUMERIC_WHERE)})

        vuln = self.detect(server, "/users", self.detector.NUMERIC)

        self.assertIsNotNone(vuln)
        self.assertEqual(vuln.get_name(), "Blind SQL injection vulnerability")
        self.assertEqual(vuln.get_severity(), severity.HIGH)
        self.assertEqual(vuln["type"], "numeric")
        self.assertEqual(vuln.get_mutant().get_token_name(), "id")
        self.assertIn('The injectable parameter is: "id"', vuln.get_desc())
        self.assertIn("HTTP method GET", vuln.get_desc())
        self.assertEqual(len(vuln.get_id()), 2)

    def test_evidence_contains_the_true_false_and_error_pages(self):
        server = self.serve({"/users": vulnerable_users(NUMERIC_WHERE)})

        vuln = self.detect(server, "/users", self.detector.NUMERIC)

        self.assertEqual(vuln["true_html"].count("<li>"), 25)
        self.assertEqual(vuln["false_html"].count("<li>"), 0)
        self.assertIn("Database error", vuln["error_html"])

    def test_single_quoted_string_injection(self):
        server = self.serve({"/accounts": vulnerable_users(STRING_WHERE)})

        vuln = self.detect(
            server, "/accounts", self.detector.STRING_SINGLE, "id=user01"
        )

        self.assertIsNotNone(vuln)
        self.assertEqual(vuln["type"], "string_single")

    def test_numeric_payloads_do_not_inject_a_single_quoted_string(self):
        server = self.serve({"/accounts": vulnerable_users(STRING_WHERE)})

        vuln = self.detect(server, "/accounts", self.detector.NUMERIC, "id=user01")

        self.assertIsNone(vuln)

    def test_double_quoted_payloads_do_not_inject_a_single_quoted_string(self):
        server = self.serve({"/accounts": vulnerable_users(STRING_WHERE)})

        vuln = self.detect(
            server, "/accounts", self.detector.STRING_DOUBLE, "id=user01"
        )

        self.assertIsNone(vuln)

    def test_injection_is_found_when_the_page_is_mostly_static(self):
        # The rows are a tiny part of the page, so true and false responses are
        # very similar and only the diff of both is compared
        server = self.serve({"/users": vulnerable_users(NUMERIC_WHERE, BIG_FOOTER)})

        vuln = self.detect(server, "/users", self.detector.NUMERIC)

        self.assertIsNotNone(vuln)
        self.assertEqual(vuln["type"], "numeric")


class TestRejectsFalsePositives(BlindSqliTestCase):
    def test_page_that_ignores_the_parameter(self):
        server = self.serve({"/static": static_page})

        self.assertIsNone(self.detect(server, "/static", self.detector.NUMERIC))

    def test_parameterized_query_is_not_injectable(self):
        server = self.serve({"/safe": parameterized_users})

        self.assertIsNone(self.detect(server, "/safe", self.detector.NUMERIC))

    def test_syntax_error_page_that_looks_like_the_true_page(self):
        pages = ScriptedPages(
            SYNTAX_ERROR, true=[MANY_USERS], false=[NO_USERS], syntax=[MANY_USERS]
        )
        server = self.serve({"/page": pages})

        self.assertIsNone(self.detect(server, "/page", self.detector.NUMERIC))

    def test_search_engine_ignoring_special_characters(self):
        pages = ScriptedPages(
            SYNTAX_ERROR,
            true=[MANY_USERS],
            false=[NO_USERS],
            syntax=[ERROR_PAGE],
            search=[MANY_USERS],
        )
        server = self.serve({"/page": pages})

        self.assertIsNone(self.detect(server, "/page", self.detector.NUMERIC))

    def test_search_engine_returning_more_results_without_special_characters(self):
        pages = ScriptedPages(
            SYNTAX_ERROR,
            true=[MANY_USERS],
            false=[NO_USERS],
            syntax=[ERROR_PAGE],
            search=[HUGE_LISTING],
        )
        server = self.serve({"/page": pages})

        self.assertIsNone(self.detect(server, "/page", self.detector.NUMERIC))

    def test_unstable_true_page(self):
        pages = ScriptedPages(
            SYNTAX_ERROR,
            true=[MANY_USERS, ERROR_PAGE],
            false=[NO_USERS],
            syntax=[ERROR_PAGE],
            search=[HUGE_LISTING[:10]],
        )
        server = self.serve({"/page": pages})

        self.assertIsNone(self.detect(server, "/page", self.detector.NUMERIC))

    def test_unstable_false_page(self):
        pages = ScriptedPages(
            SYNTAX_ERROR,
            true=[MANY_USERS],
            false=[NO_USERS, ERROR_PAGE + "x" * 500],
            syntax=[ERROR_PAGE],
            search=[ERROR_PAGE],
        )
        server = self.serve({"/page": pages})

        self.assertIsNone(self.detect(server, "/page", self.detector.NUMERIC))

    def test_confirmation_round_that_fails_after_a_success(self):
        pages = ScriptedPages(
            SYNTAX_ERROR,
            true=[MANY_USERS] * 4 + [NO_USERS],
            false=[NO_USERS],
            syntax=[ERROR_PAGE],
            search=[ERROR_PAGE],
        )
        server = self.serve({"/page": pages})

        self.assertIsNone(self.detect(server, "/page", self.detector.NUMERIC))

    def test_http_errors_never_confirm_an_injection(self):
        server = self.serve({"/page": Response(drop=True)})
        self.uri_opener.settings.set_configured_timeout(1)

        self.assertIsNone(self.detect(server, "/page", self.detector.NUMERIC))


class TestDetectorHelpers(BlindSqliTestCase):
    def test_statement_types(self):
        self.assertEqual(
            self.detector.get_statement_types(),
            ["numeric", "string_single", "string_double"],
        )

    def test_debugging_id(self):
        self.assertEqual(self.detector.get_debugging_id(), 42)

    def test_statements_are_true_and_false_pairs_for_each_type(self):
        server = self.serve({"/users": static_page})
        statements = self.detector._get_statements(mutant_for(server, "/users"))

        numeric_true, numeric_false = statements["numeric"]
        number = numeric_true.split(" ")[0]
        self.assertEqual(
            numeric_true, f"{number} OR {number}={number} OR {number}={number} "
        )
        self.assertEqual(numeric_false, f"{number} AND {number}={int(number) + 1} ")
        self.assertEqual(
            statements["string_single"][0],
            f"{number}' OR '{number}'='{number}' OR '{number}'='{number}",
        )
        self.assertEqual(
            statements["string_double"][1],
            f'{number}" AND "{number}"="{int(number) + 1}',
        )

    def test_special_characters_are_removed_and_spaces_collapsed(self):
        statement = self.detector._remove_all_special_chars('47" OR "47"="47"')

        self.assertEqual(statement, "47 OR 47 47 ")

    def test_equal_with_limit_uses_the_configured_limit(self):
        common = [f"line {i}" for i in range(90)]
        first = "\n".join(common + ["b"] * 10)
        second = "\n".join(common + ["c"] * 10)

        self.assertTrue(self.detector.equal_with_limit(first, second))

        self.detector.set_eq_limit(0.99)
        self.assertFalse(self.detector.equal_with_limit(first, second))

    def test_equal_with_limit_can_compare_only_the_differences(self):
        common = [f"line {i}" for i in range(200)]
        first = "\n".join(common + ["alpha"])
        second = "\n".join(common + ["omega"])

        self.assertTrue(self.detector.equal_with_limit(first, second))
        self.assertFalse(self.detector.equal_with_limit(first, second, True))
