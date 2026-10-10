"""
test_xurllib_api.py

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

import base64
import os
import tempfile
import unittest
from errno import EPIPE

import spnego

from w3af.core.controllers.plugins.evasion_plugin import EvasionPlugin
from w3af.core.controllers.w3af_core import w3afCore
from w3af.core.data.dc.cookie import Cookie
from w3af.core.data.dc.headers import Headers
from w3af.core.data.fuzzer.mutants.querystring_mutant import QSMutant
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.request.fuzzable_request import FuzzableRequest
from w3af.core.data.url.constants import MAX_ERROR_COUNT
from w3af.core.data.url.extended_urllib import ExtendedUrllib
from w3af.core.data.url.response_meta import SUCCESS
from w3af.core.data.url.tests.helpers.raw_handlers import EmptyTCPHandler
from w3af.core.data.url.tests.helpers.route_server import Response, RouteServer, echo
from w3af.core.data.url.tests.helpers.upper_daemon import UpperDaemon
from w3af.core.data.user_agent.random_user_agent import UA_CACHE
from w3af.core.exceptions import (
    BaseFrameworkException,
    ScanMustStopByKnownReasonExc,
    ScanMustStopByUnknownReasonExc,
    ScanMustStopException,
)

LOGGER_NAME = "w3af.core.data.url.extended_urllib"


class FailingEvasion(EvasionPlugin):
    """An evasion plugin which can't modify any request."""

    def modify_request(self, request):
        raise BaseFrameworkException("Can not modify the request")

    def get_priority(self):
        return 0


class TestExtendedUrllibAPI(unittest.TestCase):

    def setUp(self):
        self.uri_opener = ExtendedUrllib()
        self.addCleanup(self.uri_opener.end)
        self.addCleanup(self.uri_opener.settings.set_default_values)

        self.server = RouteServer.serve_for(
            self, {"/": Response(200, "index"), "/echo": echo}
        )

    def url(self, path="/"):
        return URL(self.server.url(path))

    def test_restart(self):
        self.uri_opener.stop()
        self.uri_opener.restart()

        self.assertEqual(self.uri_opener.GET(self.url()).get_body(), "index")

    def test_setup_reuses_opener_until_settings_change(self):
        self.uri_opener.setup()
        opener = self.uri_opener._opener

        self.uri_opener.setup()

        self.assertIs(self.uri_opener._opener, opener)

        self.uri_opener.settings.need_update = True
        self.uri_opener.setup()

        self.assertIsNot(self.uri_opener._opener, opener)

    def test_send_clean(self):
        freq = FuzzableRequest(self.url("/echo?id=1"))
        mutant = QSMutant.create_mutants(freq, ["payload1234"], [], False, {})[0]

        response, clean_body = self.uri_opener.send_clean(mutant)

        self.assertIn("id=payload1234", response.get_body())
        self.assertNotIn("payload1234", clean_body)
        self.assertIn("id=", clean_body)

    def test_send_raw_request_uses_the_real_content_length(self):
        head = (
            f"POST {self.server.url('/echo')} HTTP/1.1\n"
            f"Host: 127.0.0.1\n"
            f"Content-Length: 1\n"
        )

        response = self.uri_opener.send_raw_request(head, "a=123")

        self.assertIn("a=123", response.get_body())
        self.assertEqual(self.server.requests[-1].headers["Content-Length"], "5")

    def test_send_raw_request_without_body(self):
        head = f"GET {self.server.url('/echo')} HTTP/1.1\nHost: 127.0.0.1\n"

        response = self.uri_opener.send_raw_request(head, "")

        self.assertEqual(response.get_code(), 200)
        self.assertEqual(self.server.requests[-1].method, "GET")
        self.assertEqual(self.server.requests[-1].body, b"")

    def test_new_sessions_are_unique(self):
        self.assertNotEqual(
            self.uri_opener.get_new_session(), self.uri_opener.get_new_session()
        )

    def test_send_mutant_with_cookie_and_callback(self):
        freq = FuzzableRequest(self.url("/echo"), cookie=Cookie("session=abc"))
        received = []

        response = self.uri_opener.send_mutant(
            freq, callback=lambda mutant, resp: received.append((mutant, resp))
        )

        self.assertIn("Cookie: session=abc", response.get_body())
        self.assertEqual(received, [(freq, response)])

    def test_send_mutant_without_cookies(self):
        freq = FuzzableRequest(self.url("/echo"), cookie=Cookie("session=abc"))

        response = self.uri_opener.send_mutant(freq, cookies=False)

        self.assertNotIn("session=abc", response.get_body())

    def test_parameter_types_are_validated(self):
        url = self.url()

        for method in (self.uri_opener.GET, self.uri_opener.POST, self.uri_opener.PUT):
            self.assertRaises(TypeError, method, self.server.url())
            self.assertRaises(TypeError, method, url, headers={"A": "b"})

    def test_any_method(self):
        put = self.uri_opener.PUT

        response = put(
            self.url("/echo"),
            data="a=1",
            headers=Headers([("X", "y")]),
            timeout=1,
        )

        self.assertEqual(put.__doc__, "Send PUT HTTP request")
        self.assertEqual(response.get_code(), 200)

        request = self.server.requests[-1]
        self.assertEqual(request.method, "PUT")
        self.assertEqual(request.body, b"a=1")
        self.assertEqual(request.headers["X"], "y")

    def test_post_serializes_non_text_data(self):
        response = self.uri_opener.POST(self.url("/echo"), data=123, cache=False)

        self.assertIn("123", response.get_body())
        self.assertEqual(self.server.requests[-1].body, b"123")

    def test_rtt_by_debugging_id(self):
        self.assertIsNone(self.uri_opener.get_rtt_for_debugging_id(None))
        self.assertIsNone(self.uri_opener.get_rtt_for_debugging_id("unknown"))

        first = self.uri_opener.GET(self.url(), debugging_id="did")
        second = self.uri_opener.GET(self.url(), debugging_id="did")

        self.assertAlmostEqual(
            self.uri_opener.get_rtt_for_debugging_id("did"),
            first.get_wait_time() + second.get_wait_time(),
        )

    def test_random_user_agent(self):
        self.uri_opener.settings.set_rand_user_agent(True)

        self.uri_opener.GET(self.url())

        user_agent = self.server.requests[-1].headers["User-Agent"]
        self.assertNotEqual(user_agent, "w3af.org")
        self.assertIn(user_agent, UA_CACHE)

    def test_long_post_data_is_logged_truncated(self):
        data = "a=" + "x" * 100 + "\r\n"

        with self.assertLogs(LOGGER_NAME, "DEBUG") as logs:
            self.uri_opener.POST(self.url("/echo"), data=data)

        self.assertTrue(
            any(f'with data: "a={"x" * 73}..."' in line for line in logs.output)
        )

    def test_grep_queue(self):
        grepped = []
        self.uri_opener.set_grep_queue_put(
            lambda request, response: grepped.append(response)
        )

        response = self.uri_opener.GET(self.url())
        self.uri_opener.GET(self.url(), grep=False)

        self.assertEqual(grepped, [response])

    def test_failing_evasion_plugin(self):
        self.uri_opener.set_evasion_plugins([FailingEvasion()])

        with self.assertLogs(LOGGER_NAME, "ERROR") as logs:
            response = self.uri_opener.GET(self.url())

        self.assertEqual(response.get_body(), "index")
        self.assertIn('Evasion plugin "FailingEvasion" failed', logs.output[0])


class TestWorkerPoolSize(unittest.TestCase):

    def setUp(self):
        self.uri_opener = ExtendedUrllib()
        self.addCleanup(self.uri_opener.end)
        self.addCleanup(self.uri_opener.settings.set_default_values)
        self.uri_opener.settings.set_max_http_retries(0)

        self.server = RouteServer.serve_for(
            self, {"/": Response(200, "ok"), "/fail": Response(drop=True)}
        )

        self.w3af_core = w3afCore()
        self.worker_pool = self.w3af_core.worker_pool
        self.addCleanup(self.worker_pool.terminate_join)

    def fail(self, times):
        for _ in range(times):
            try:
                self.uri_opener.GET(URL(self.server.url("/fail")))
            except BaseFrameworkException:
                pass

    def adjustments(self, logs):
        return [line for line in logs.output if "the worker pool size" in line]

    def test_increase_without_errors(self):
        start = self.worker_pool.get_worker_count()
        self.configure_worker_pool()

        with self.assertLogs(LOGGER_NAME, "DEBUG") as logs:
            self.uri_opener.GET(URL(self.server.url()))
            # Only one adjustment every 45 seconds
            self.uri_opener.GET(URL(self.server.url()))

        self.assertEqual(self.worker_pool.get_worker_count(), start + 1)
        self.assertEqual(len(self.adjustments(logs)), 1)

    def test_decrease_on_errors(self):
        start = self.worker_pool.get_worker_count()

        # These errors happen before the core is set, no adjustments yet
        self.fail(3)
        self.configure_worker_pool()

        with self.assertLogs(LOGGER_NAME, "DEBUG") as logs:
            self.uri_opener.GET(URL(self.server.url()))

        # Decreasing the pool size happens when the workers finish their
        # current task, only the decision is immediate
        self.assertEqual(
            self.adjustments(logs),
            [
                (
                    f"DEBUG:{LOGGER_NAME}:Decreased the worker pool size to"
                    f" {start - 2} (error rate: 3%)"
                )
            ],
        )

    def test_no_change_on_some_errors(self):
        start = self.worker_pool.get_worker_count()

        self.fail(2)
        self.configure_worker_pool()

        with self.assertLogs(LOGGER_NAME, "DEBUG") as logs:
            self.uri_opener.GET(URL(self.server.url()))

        self.assertEqual(self.adjustments(logs), [])
        self.assertEqual(self.worker_pool.get_worker_count(), start)

    def configure_worker_pool(self):
        self.uri_opener.set_worker_pool_provider(
            lambda: self.worker_pool,
            self.w3af_core.MIN_WORKER_THREADS,
            self.w3af_core.MAX_WORKER_THREADS,
        )


class TestHandlerErrors(unittest.TestCase):
    """
    The HTTP handlers raise urllib's HTTPError in some cases, these must be
    returned as regular HTTP responses.
    """

    def setUp(self):
        self.uri_opener = ExtendedUrllib()
        self.addCleanup(self.uri_opener.end)
        self.addCleanup(self.uri_opener.settings.set_default_values)

        with tempfile.NamedTemporaryFile("w", delete=False) as user_file:
            user_file.write("DOMAIN:user:pass\n")
        self.addCleanup(os.unlink, user_file.name)

        previous = os.environ.get("NTLM_USER_FILE")
        os.environ["NTLM_USER_FILE"] = user_file.name
        if previous is None:
            self.addCleanup(os.environ.pop, "NTLM_USER_FILE")
        else:
            self.addCleanup(os.environ.__setitem__, "NTLM_USER_FILE", previous)

    def test_ntlm_handler_gives_up(self):
        negotiate = spnego.client("DOMAIN\\user", "pass", protocol="ntlm").step()

        def always_challenge(request):
            challenge = spnego.server(protocol="ntlm").step(negotiate)
            token = base64.b64encode(challenge).decode("ascii")
            return Response(401, "", headers=[("WWW-Authenticate", f"NTLM {token}")])

        server = RouteServer.serve_for(self, {"/": always_challenge})
        self.uri_opener.settings.set_ntlm_auth(server.url(), "DOMAIN", "user", "pass")

        response = self.uri_opener.GET(URL(server.url()))

        self.assertEqual(response.get_code(), 401)
        self.assertIsNotNone(response.id)
        self.assertGreater(len(server.requests), 1)


class TestConnectionErrors(unittest.TestCase):

    def test_server_root_path_unreachable(self):
        """
        The root path check is sent after ten consecutive errors, when it
        fails the scan must stop.
        """
        uri_opener = ExtendedUrllib()
        self.addCleanup(uri_opener.end)
        self.addCleanup(uri_opener.settings.set_default_values)
        uri_opener.settings.set_max_http_retries(0)

        daemon = UpperDaemon(EmptyTCPHandler)
        daemon.start()
        daemon.wait_for_start()

        url = URL(f"http://127.0.0.1:{daemon.get_port()}/")

        with self.assertLogs(LOGGER_NAME, "DEBUG") as logs:
            for _ in range(10):
                try:
                    uri_opener.GET(url)
                except (BaseFrameworkException, ScanMustStopException):
                    pass

        self.assertTrue(any("is UNREACHABLE due to" in line for line in logs.output))
        self.assertIsInstance(uri_opener._stop_exception, ScanMustStopByKnownReasonExc)

    def test_unknown_error_reason(self):
        """
        Socket errors with unexpected error numbers (a broken pipe, for
        example) stop the scan with the messages of the last responses.
        """
        uri_opener = ExtendedUrllib()
        self.addCleanup(uri_opener.end)

        broken_pipe = BrokenPipeError(EPIPE, "Broken pipe")

        with self.assertRaises(ScanMustStopByUnknownReasonExc) as raised:
            uri_opener._handle_error_count_exceeded(broken_pipe)

        self.assertIs(uri_opener._stop_exception, raised.exception)
        self.assertEqual(raised.exception.errs, [SUCCESS] * MAX_ERROR_COUNT)
