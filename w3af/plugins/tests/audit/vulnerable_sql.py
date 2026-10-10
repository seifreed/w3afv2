"""
vulnerable_sql.py

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

import collections
import enum
import html
import sqlite3
import time

from w3af.plugins.tests.audit.vulnerable_responses import html_page, request_params

SCHEMA = """
CREATE TABLE records (
    id INTEGER, name TEXT, password TEXT, msg TEXT, balance INTEGER, created TEXT
);
INSERT INTO records VALUES (1, 'pablo', 'secret', 'hello', 10, '2013-01-01');
INSERT INTO records VALUES (2, 'foobar', 'hunter2', 'world', 20, '2014-02-02');
INSERT INTO records VALUES (3, 'admin', 'admin', 'again', 30, '2015-03-03');
CREATE TABLE log (msg TEXT, target TEXT);
"""

NO_RESULTS = "No records found"


class ErrorMode(enum.Enum):
    """
    What the vulnerable application does when the database rejects a query.
    """

    SHOW_200 = enum.auto()
    SHOW_500 = enum.auto()
    DEFAULT_PAGE = enum.auto()
    IDENTICAL_PAGE = enum.auto()


def _sleep(seconds):
    time.sleep(seconds)
    return 0


def _fail():
    raise ValueError("deliberate runtime error")


def open_database():
    """
    :return: A fresh in-memory SQLite database with the application data and
             the SLEEP() and FAIL() functions that injected payloads rely on.
    """
    connection = sqlite3.connect(":memory:")
    connection.executescript(SCHEMA)
    connection.create_function("SLEEP", 1, _sleep)
    connection.create_function("FAIL", 0, _fail)
    return connection


def run_query(query):
    """
    Execute the query in a fresh database, as the application would do.

    :return: The result rows, or the affected row count for a data change
    """
    connection = open_database()
    try:
        cursor = connection.execute(query)
        if cursor.description is None:
            return cursor.rowcount
        return cursor.fetchall()
    finally:
        connection.close()


def render_result(result):
    if isinstance(result, int):
        return f"Affected rows: {result}"

    if not result:
        return NO_RESULTS

    rows = "".join(f"<tr><td>{html.escape(str(row))}</td></tr>" for row in result)
    return f"<table>{rows}</table>"


class SqlQueryPage:
    """
    A page which concatenates the request parameters into a SQL query template,
    runs the query against a real SQLite database and renders the result.
    """

    def __init__(self, query_template, error_mode=ErrorMode.SHOW_200):
        self.query_template = query_template
        self.error_mode = error_mode

    def __call__(self, mock_response, request, uri, response_headers):
        params = collections.defaultdict(str, request_params(request))
        query = self.query_template.format_map(params)

        try:
            result = run_query(query)
        except sqlite3.Error as error:
            return self._error_response(response_headers, error)

        if self.error_mode is ErrorMode.IDENTICAL_PAGE:
            return html_page(response_headers, "Request processed")

        return html_page(response_headers, render_result(result))

    def _error_response(self, response_headers, error):
        if self.error_mode is ErrorMode.SHOW_200:
            return html_page(response_headers, f"Database error: {error}")

        if self.error_mode is ErrorMode.SHOW_500:
            return html_page(response_headers, f"Database error: {error}", status=500)

        if self.error_mode is ErrorMode.IDENTICAL_PAGE:
            return html_page(response_headers, "Request processed")

        return html_page(response_headers, NO_RESULTS)


class FormOrQuery:
    """
    A page that shows an HTML form until the form field is sent, and then
    runs the vulnerable query.
    """

    def __init__(self, form_html, field, query_page):
        self.form_html = form_html
        self.field = field
        self.query_page = query_page

    def __call__(self, mock_response, request, uri, response_headers):
        if self.field in request_params(request):
            return self.query_page(mock_response, request, uri, response_headers)
        return html_page(response_headers, self.form_html)
