"""
test_eval.py

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

from w3af.plugins.tests.audit.vulnerable_responses import (
    html_page,
    request_param,
    sleep_for_payload,
)
from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest

EVAL_URL = "http://mock/audit/eval_vuln/"
PHP_EVAL_URL = "http://mock/phpwn/eval.php"
VULN_NAME = "eval() input injection vulnerability"

PYTHON_PRINT = r"print\('(\w+)'\*(\d+)\)"
PHP_ECHO = r"echo str_repeat\('(\w+)',(\d+)\);"
PYTHON_SLEEP = r"^__import__\('time'\)\.sleep\((\d+)\)$"
PHP_SLEEP = r"^sleep\((\d+)\);$"

PHP_EVAL_TARGET = (
    f"{PHP_EVAL_URL}?sanitization_level=none"
    "&sanitization_type=keyword"
    "&query_results=all_rows"
    "&inject_string=abc"
    "&custom_inject="
    "&submit=Inject%21"
)


def evaluate_print(code, print_regex):
    """Emulate the output of an evaluated print/echo statement."""
    match = re.fullmatch(print_regex, code)
    if match is None:
        return f"Syntax error in {code}"
    return match.group(1) * int(match.group(2))


def python_echo(mock_response, request, uri, response_headers):
    """Evaluate the text parameter as Python code and print the result."""
    result = evaluate_print(request_param(request, "text"), PYTHON_PRINT)
    return html_page(response_headers, result)


def python_blind(mock_response, request, uri, response_headers):
    """Evaluate the text parameter as Python code without printing it."""
    sleep_for_payload(request_param(request, "text"), PYTHON_SLEEP)
    return html_page(response_headers, "Done")


def php_echo(mock_response, request, uri, response_headers):
    """Evaluate the custom_inject parameter as PHP code."""
    result = evaluate_print(request_param(request, "custom_inject"), PHP_ECHO)
    return html_page(response_headers, result)


def php_sleep(mock_response, request, uri, response_headers):
    """Evaluate the custom_inject parameter as PHP code, with no output."""
    sleep_for_payload(request_param(request, "custom_inject"), PHP_SLEEP)
    return html_page(response_headers, "Done")


def plugin_config(use_echo):
    return {
        "audit": (
            PluginConfig(
                "eval",
                ("use_echo", use_echo, PluginConfig.BOOL),
                ("use_time_delay", not use_echo, PluginConfig.BOOL),
            ),
        ),
    }


class TestEval(PluginTest):

    target_echo = f"{EVAL_URL}eval_double.py"
    target_delay = f"{EVAL_URL}eval_blind.py"
    target_url = target_echo

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(re.compile(f"{target_echo}.*"), python_echo),
        MockResponse(re.compile(f"{target_delay}.*"), python_blind),
    ]

    def assert_text_vuln(self, url):
        vulns = self.kb.get("eval", "eval")
        self.assertEqual(1, len(vulns))

        vuln = vulns[0]
        self.assertEqual(VULN_NAME, vuln.get_name())
        self.assertEqual("text", vuln.get_token_name())
        self.assertEqual(url, str(vuln.get_url()))

    def test_found_eval_echo(self):
        self._scan(self.target_echo + "?text=1", plugin_config(True))
        self.assert_text_vuln(self.target_echo)

    def test_found_eval_delay(self):
        self._scan(self.target_delay + "?text=1", plugin_config(False))
        self.assert_text_vuln(self.target_delay)

    def test_echo_finding_skips_delay_tests(self):
        self._scan(self.target_echo + "?text=1", {"audit": (PluginConfig("eval"),)})
        self.assert_text_vuln(self.target_echo)

    def test_echo_page_has_no_delay(self):
        self._scan(self.target_echo + "?text=1", plugin_config(False))
        self.assertEqual([], self.kb.get("eval", "eval"))


class TestPHPEchoEval(PluginTest):

    target_url = PHP_EVAL_TARGET

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(re.compile(f"{PHP_EVAL_URL}.*"), php_echo),
    ]

    def test_found_eval_echo_php(self):
        self._scan(self.target_url, plugin_config(True))

        vulns = self.kb.get("eval", "eval")
        self.assertEqual(["custom_inject"], [v.get_token_name() for v in vulns])


class TestPHPSleepEval(PluginTest):

    target_url = PHP_EVAL_TARGET

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(re.compile(f"{PHP_EVAL_URL}.*"), php_sleep),
    ]

    def test_found_eval_sleep_php(self):
        self._scan(self.target_url, plugin_config(False))

        vulns = self.kb.get("eval", "eval")
        self.assertEqual(["custom_inject"], [v.get_token_name() for v in vulns])
