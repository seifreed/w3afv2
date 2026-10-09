"""
sqli_site.py

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

import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Self
from urllib.parse import parse_qs, urlsplit

SQLI_PATH = "/audit/sql_injection/"
MAX_HOLD_SECONDS = 60

INTEGER_QS = "where_integer_qs.py"
STRING_QS = "where_string_single_qs.py"
INTEGER_FORM = "where_integer_form.py"
VULNERABLE_PAGES = (INTEGER_QS, STRING_QS, INTEGER_FORM)

PRIVATE_IP = "10.1.2.3"

SQL_ERROR = (
    "You have an error in your SQL syntax; check the manual that corresponds"
    " to your MySQL server version for the right syntax to use"
)

INDEX_BODY = f"""<html><head><title>SQL injection</title></head><body>
<ul>
<li><a href="{INTEGER_QS}?id=1">Integer in query string</a></li>
<li><a href="{STRING_QS}?uname=pablo">String in query string</a></li>
<li><a href="{INTEGER_FORM}">Integer in form</a></li>
</ul>
<p>Database server at {PRIVATE_IP}</p>
</body></html>"""

FORM_BODY = f"""<html><body>
<form action="{INTEGER_FORM}" method="POST">
<input type="text" name="text" />
<input type="submit" name="Submit" value="Submit" />
</form>
</body></html>"""

NOT_FOUND_BODY = "<html><body>Not found</body></html>"


def query_result(value: str, is_integer: bool) -> str:
    """
    Emulate a query that concatenates the user input without escaping it
    """
    quoted = value if is_integer else f"'{value}'"
    if quoted.count("'") % 2 == 1 or '"' in value:
        return f"<html><body>{SQL_ERROR} near '{value}' at line 1</body></html>"

    return f"<html><body>Results for {value}</body></html>"


class SQLInjectionSite:
    """
    A local web application with SQL injection vulnerabilities which mirrors
    the moth /audit/sql_injection/ pages.

    When hold_requests is set, every request except the index is held until
    release() is called, which keeps a scan running for as long as a test
    needs it.
    """

    def __init__(self, hold_requests: bool = False) -> None:
        self.released = threading.Event()
        if not hold_requests:
            self.released.set()

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), self._handler_class())
        self.server.daemon_threads = True
        self._thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    @property
    def root_url(self) -> str:
        return f"http://127.0.0.1:{self.server.server_address[1]}/"

    @property
    def url(self) -> str:
        return f"{self.root_url[:-1]}{SQLI_PATH}"

    def vulnerable_urls(self) -> list[str]:
        return [f"{self.url}{page}" for page in VULNERABLE_PAGES]

    def start(self) -> None:
        self._thread.start()

    def release(self) -> None:
        self.released.set()

    def close(self) -> None:
        self.release()
        self.server.shutdown()
        self.server.server_close()

    def __enter__(self) -> Self:
        self.start()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    @classmethod
    def serve_for(
        cls, test_case: unittest.TestCase, hold_requests: bool = False
    ) -> Self:
        """
        Start a site which is closed when test_case finishes
        """
        site = cls(hold_requests=hold_requests)
        site.start()
        test_case.addCleanup(site.close)
        return site

    def _handler_class(self) -> type[BaseHTTPRequestHandler]:
        released = self.released

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                path, query = self._split()
                if path != SQLI_PATH:
                    released.wait(MAX_HOLD_SECONDS)
                self._route(path, query)

            def do_POST(self) -> None:
                released.wait(MAX_HOLD_SECONDS)
                path, _ = self._split()
                length = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(length).decode("utf-8", "replace")
                self._route(path, parse_qs(body, keep_blank_values=True))

            def _split(self) -> tuple[str, dict[str, list[str]]]:
                parts = urlsplit(self.path)
                return parts.path, parse_qs(parts.query, keep_blank_values=True)

            def _route(self, path: str, params: dict[str, list[str]]) -> None:
                page = path.removeprefix(SQLI_PATH)

                if path == SQLI_PATH:
                    self._reply(200, INDEX_BODY)
                elif page == INTEGER_QS:
                    self._reply(200, query_result(self._param(params, "id"), True))
                elif page == STRING_QS:
                    self._reply(200, query_result(self._param(params, "uname"), False))
                elif page == INTEGER_FORM and "text" in params:
                    self._reply(200, query_result(self._param(params, "text"), True))
                elif page == INTEGER_FORM:
                    self._reply(200, FORM_BODY)
                else:
                    self._reply(404, NOT_FOUND_BODY)

            @staticmethod
            def _param(params: dict[str, list[str]], name: str) -> str:
                return params.get(name, [""])[0]

            def _reply(self, code: int, body: str) -> None:
                encoded = body.encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

            def log_message(self, *args: object) -> None:
                """Keep the test output clean."""

        return Handler
