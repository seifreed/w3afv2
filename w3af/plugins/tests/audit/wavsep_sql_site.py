"""
wavsep_sql_site.py

Copyright 2026 w3af contributors

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
from dataclasses import dataclass

from w3af.plugins.tests.audit.vulnerable_sql import ErrorMode, SqlQueryPage
from w3af.plugins.tests.helper import MockResponse

SELECT = "SELECT * FROM records WHERE "
UPDATE = "UPDATE records SET msg = 'updated' WHERE "
QUOTED_ORDER_BY = (
    "SELECT * FROM records ORDER BY CASE WHEN ('{orderby}') THEN id ELSE FAIL() END"
)

PARAM_DEFAULTS = {
    "transactionDate": "2013-01-01",
    "orderby": "id",
}
NUMERIC_PARAMS = {"transactionId", "msgId", "msgid", "minBalanace"}


@dataclass(frozen=True)
class SqlCase:
    """
    A vulnerable page: the SQL query it builds from the request parameters.
    """

    stem: str
    params: tuple[str, ...]
    query_template: str

    def file_name(self, suffix):
        return f"{self.stem}-{suffix}.jsp"


DETECTION_CASES = (
    SqlCase(
        "Case01-InjectionInLogin-String-LoginBypass",
        ("username", "password"),
        SELECT + "name = '{username}' AND password = '{password}'",
    ),
    SqlCase(
        "Case02-InjectionInSearch-String-UnionExploit",
        ("msg",),
        SELECT + "msg = '{msg}'",
    ),
    SqlCase(
        "Case03-InjectionInCalc-String-BooleanExploit",
        ("username",),
        SELECT + "name = '{username}'",
    ),
    SqlCase(
        "Case04-InjectionInUpdate-String-CommandInjection",
        ("msg",),
        UPDATE + "msg = '{msg}'",
    ),
    SqlCase(
        "Case05-InjectionInSearchOrderBy-String-BinaryDeliberateRuntimeError",
        ("orderby",),
        QUOTED_ORDER_BY,
    ),
    SqlCase(
        "Case06-InjectionInView-Numeric-PermissionBypass",
        ("transactionId",),
        SELECT + "id = '{transactionId}'",
    ),
    SqlCase(
        "Case07-InjectionInSearch-Numeric-UnionExploit",
        ("msgId",),
        SELECT + "id = '{msgId}'",
    ),
    SqlCase(
        "Case08-InjectionInCalc-Numeric-BooleanExploit",
        ("minBalanace",),
        SELECT + "balance > '{minBalanace}'",
    ),
    SqlCase(
        "Case09-InjectionInUpdate-Numeric-CommandInjection",
        ("msgid",),
        UPDATE + "id = '{msgid}'",
    ),
    SqlCase(
        "Case10-InjectionInSearchOrderBy-Numeric-BinaryDeliberateRuntimeError",
        ("orderby",),
        QUOTED_ORDER_BY,
    ),
    SqlCase(
        "Case11-InjectionInView-Date-PermissionBypass",
        ("transactionDate",),
        SELECT + "created = '{transactionDate}'",
    ),
    SqlCase(
        "Case12-InjectionInSearch-Date-UnionExploit",
        ("transactionDate",),
        SELECT + "created = '{transactionDate}'",
    ),
    SqlCase(
        "Case13-InjectionInCalc-Date-BooleanExploit",
        ("transactionDate",),
        SELECT + "created >= '{transactionDate}'",
    ),
    SqlCase(
        "Case14-InjectionInUpdate-Date-CommandInjection",
        ("transactionDate",),
        UPDATE + "created = '{transactionDate}'",
    ),
    SqlCase(
        "Case15-InjectionInSearch-DateWithoutQuotes-UnionExploit",
        ("transactionDate",),
        SELECT + "created = {transactionDate}",
    ),
    SqlCase(
        "Case16-InjectionInView-NumericWithoutQuotes-PermissionBypass",
        ("transactionId",),
        SELECT + "id = {transactionId}",
    ),
    SqlCase(
        "Case17-InjectionInSearch-NumericWithoutQuotes-UnionExploit",
        ("msgId",),
        SELECT + "id = {msgId}",
    ),
    SqlCase(
        "Case18-InjectionInCalc-NumericWithoutQuotes-BooleanExploit",
        ("minBalanace",),
        SELECT + "balance > {minBalanace}",
    ),
    SqlCase(
        "Case19-InjectionInUpdate-NumericWithoutQuotes-CommandInjection",
        ("msgid",),
        UPDATE + "id = {msgid}",
    ),
)

IDENTICAL_BLIND_CASES = (
    SqlCase(
        "Case01-InjectionInView-Numeric-Blind",
        ("transactionId",),
        SELECT + "id = '{transactionId}'",
    ),
    SqlCase(
        "Case02-InjectionInView-String-Blind",
        ("username",),
        SELECT + "name = '{username}'",
    ),
    SqlCase(
        "Case03-InjectionInView-Date-Blind",
        ("transactionDate",),
        SELECT + "created = '{transactionDate}'",
    ),
)

IDENTICAL_TIME_DELAY_CASES = (
    SqlCase(
        "Case04-InjectionInUpdate-Numeric-TimeDelayExploit",
        ("transactionId",),
        UPDATE + "id = '{transactionId}'",
    ),
    SqlCase(
        "Case05-InjectionInUpdate-String-TimeDelayExploit",
        ("description",),
        UPDATE + "msg = '{description}'",
    ),
    SqlCase(
        "Case06-InjectionInUpdate-Date-TimeDelayExploit",
        ("transactionDate",),
        UPDATE + "created = '{transactionDate}'",
    ),
    SqlCase(
        "Case07-InjectionInUpdate-NumericWithoutQuotes-TimeDelayExploit",
        ("transactionId",),
        UPDATE + "id = {transactionId}",
    ),
    SqlCase(
        "Case08-InjectionInUpdate-DateWithoutQuotes-TimeDelayExploit",
        ("transactionDate",),
        UPDATE + "created = {transactionDate}",
    ),
)

EXPERIMENTAL_CASES = (
    SqlCase(
        "Case01-InjectionInInsertValues-String-BinaryDeliberateRuntimeError",
        ("msg", "target"),
        "INSERT INTO log VALUES ('{msg}', '{target}')",
    ),
)


@dataclass(frozen=True)
class Page:
    """
    A case served with the application behaviour of its suite.
    """

    file_name: str
    case: SqlCase
    error_mode: ErrorMode


def param_default(param):
    if param in PARAM_DEFAULTS:
        return PARAM_DEFAULTS[param]
    return "1" if param in NUMERIC_PARAMS else "textvalue"


class SuiteSite:
    """
    The responses that serve a WAVSEP suite under base_url, reading the
    parameters from the query string (GET) or from the body (POST).
    """

    def __init__(self, base_url, pages, use_post):
        self.base_url = base_url
        self.pages = pages
        self.use_post = use_post

    @property
    def expected_vulns(self):
        return {
            (page.file_name, param) for page in self.pages for param in page.case.params
        }

    def responses(self):
        responses = [MockResponse(self.base_url, self._index_body())]
        method = "POST" if self.use_post else "GET"

        for page in self.pages:
            handler = SqlQueryPage(page.case.query_template, page.error_mode)
            url = re.compile(re.escape(self.base_url + page.file_name) + r"(\?.*)?$")
            responses.append(MockResponse(url, handler, method=method))

        return responses

    def _index_body(self):
        render = self._form if self.use_post else self._link
        return "".join(render(page) for page in self.pages)

    @staticmethod
    def _link(page):
        query = "&".join(f"{p}={param_default(p)}" for p in page.case.params)
        return f'<a href="{page.file_name}?{query}">{page.file_name}</a><br/>'

    @staticmethod
    def _form(page):
        inputs = "".join(
            f'<input type="text" name="{p}" value="{param_default(p)}"/>'
            for p in page.case.params
        )
        return (
            f'<form action="{page.file_name}" method="POST">{inputs}'
            '<input type="submit" value="send"/></form>'
        )


def suite_site(base_url, cases, suffix, error_mode, use_post):
    pages = [Page(case.file_name(suffix), case, error_mode) for case in cases]
    return SuiteSite(base_url, pages, use_post)


def identical_suite_site(base_url, use_post):
    """
    The "identical responses" suite: three cases which blind SQL injection
    response diffs find, and five which only time delays can find.
    """
    blind = [
        Page(
            case.file_name("200ValidResponseWithDefaultOnException"),
            case,
            ErrorMode.DEFAULT_PAGE,
        )
        for case in IDENTICAL_BLIND_CASES
    ]
    delayed = [
        Page(case.file_name("200Identical"), case, ErrorMode.IDENTICAL_PAGE)
        for case in IDENTICAL_TIME_DELAY_CASES
    ]
    return SuiteSite(base_url, blind + delayed, use_post)
