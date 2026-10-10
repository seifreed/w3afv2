"""
Real HTTP applications used to test the blind SQL injection detection.

The vulnerable ones evaluate the injected value as part of an SQL condition,
the others answer with pre-defined pages depending on the kind
of statement that reaches them.
"""

import threading
import time
from urllib.parse import parse_qs, urlsplit

from w3af.core.controllers.sql_tools.tests.where_clause import (
    SqlSyntaxError,
    WhereClause,
)
from w3af.core.data.fuzzer.mutants.querystring_mutant import QSMutant
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.request.fuzzable_request import FuzzableRequest
from w3af.core.data.url.tests.helpers.route_server import (
    RecordedRequest,
    Response,
    RouteServer,
)

USER_COUNT = 25
SPECIAL_CHARS = "\"'="


def param(request: RecordedRequest, name: str = "id") -> str:
    query = parse_qs(urlsplit(request.path).query, keep_blank_values=True)
    return query.get(name, [""])[0]


def users_page(names, footer=""):
    items = "".join(f"<li>{name}</li>" for name in names)
    return (
        "<html><head><title>Users</title></head><body><h1>User directory</h1>"
        f"<ul>{items}</ul>{footer}</body></html>"
    )


USERS = [{"id": i, "name": f"user{i:02d}"} for i in range(1, USER_COUNT + 1)]


def find_users(where_clause_template: str, value: str) -> list[str]:
    """
    Find the users with a condition that places the value inside the SQL
    statement without escaping it, which is the root cause of SQL injection.
    """
    condition = where_clause_template % value
    return [str(u["name"]) for u in USERS if WhereClause(condition, u).matches()]


def vulnerable_users(where_clause_template: str, footer: str = ""):
    def respond(request: RecordedRequest) -> Response:
        try:
            names = find_users(where_clause_template, param(request))
        except SqlSyntaxError:
            return Response(200, "<html><body>Database error</body></html>")
        return Response(200, users_page(names, footer))

    return respond


def parameterized_users(request: RecordedRequest) -> Response:
    """The safe version: the value is compared as data, never as SQL."""
    names = [str(u["name"]) for u in USERS if str(u["id"]) == param(request)]
    return Response(200, users_page(names))


def static_page(request: RecordedRequest) -> Response:
    return Response(200, users_page(["always", "the", "same"]))


class ScriptedPages:
    """
    Answers depending on the kind of statement the value contains, using the
    next page in the script of that kind (the last one is repeated).

    Kinds: syntax (SYNTAX_ERROR), false (AND), true (OR with quotes or equal
    signs) and search (OR without any of them).
    """

    def __init__(self, syntax_error: str, **pages: list[str]):
        self.syntax_error = syntax_error
        self.pages = pages
        self.sent: dict[str, int] = {}
        self.lock = threading.Lock()

    def kind(self, value: str) -> str:
        if value == self.syntax_error:
            return "syntax"
        if " AND " in value:
            return "false"
        has_special = any(char in value for char in SPECIAL_CHARS)
        return "true" if has_special else "search"

    def __call__(self, request: RecordedRequest) -> Response:
        kind = self.kind(param(request))
        with self.lock:
            index = self.sent.get(kind, 0)
            self.sent[kind] = index + 1

        scripted = self.pages[kind]
        return Response(200, scripted[min(index, len(scripted) - 1)])


class SlowSql:
    """Sleeps the seconds requested with sleep(N), like a vulnerable database."""

    def __call__(self, request: RecordedRequest) -> Response:
        value = param(request)
        start = value.lower().find("sleep(")
        if start >= 0:
            seconds = value[start + len("sleep(") :].split(")")[0]
            time.sleep(float(seconds))
        return Response(200, "<html><body>done</body></html>")


def mutant_for(server: RouteServer, path: str, query: str = "id=1"):
    """
    :return: A real query string mutant that injects the "id" parameter
    """
    url = URL(server.url(f"{path}?{query}"))
    mutant = QSMutant(FuzzableRequest(url))
    mutant.set_dc(url.querystring)
    mutant.set_token(("id", 0))
    return mutant
