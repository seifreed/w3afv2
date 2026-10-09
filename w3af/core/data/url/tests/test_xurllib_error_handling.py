"""
test_xurllib_error_handling.py

Copyright 2011 Andres Riancho

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

import socketserver
import threading
import time
import unittest
from typing import ClassVar

import pytest

from w3af.core.data.constants.file_patterns import FILE_PATTERNS
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.url.constants import SOCKET_ERROR_DELAY
from w3af.core.data.url.exceptions import HTTPRequestException
from w3af.core.data.url.extended_urllib import ExtendedUrllib
from w3af.core.data.url.tests.helpers.local_server import LocalServer, Reply
from w3af.core.data.url.tests.helpers.raw_handlers import EmptyTCPHandler
from w3af.core.data.url.tests.helpers.upper_daemon import (
    ThreadingUpperDaemon,
    UpperDaemon,
)
from w3af.core.exceptions import (
    ScanMustStopByKnownReasonExc,
    ScanMustStopException,
)
from w3af.plugins.tests.helper import PluginConfig, PluginTest

TIMEOUT_SECS = 1
ALL_BUCKETS = (0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100)


class SlowResponder:
    def __init__(self, delay):
        self.delay = delay

    def __call__(self, request):
        time.sleep(self.delay)
        return Reply(200, "slow")


class GatedFailure:
    """
    Drop every connection without answering. The `gated_call`-th request is
    held until `release` is set.
    """

    def __init__(self, gated_call):
        self.gated_call = gated_call
        self.calls = 0
        self.received = threading.Event()
        self.release = threading.Event()

    def __call__(self, request):
        self.calls += 1

        if self.calls == self.gated_call:
            self.received.set()
            self.release.wait(60)

        return Reply(drop=True)


@pytest.mark.smoke
class TestXUrllibDelayOnError(unittest.TestCase):

    def setUp(self):
        self.uri_opener = ExtendedUrllib()
        self.addCleanup(self.uri_opener.end)
        self.addCleanup(self.uri_opener.settings.set_default_values)

        # No retries means that the tests are easier to read/understand
        self.uri_opener.settings.set_max_http_retries(0)

    def send(self, url):
        start = time.monotonic()
        try:
            self.uri_opener.GET(url, cache=False)
        except HTTPRequestException:
            pass
        return time.monotonic() - start

    def test_increasing_delay_on_errors(self):
        self.assertEqual(
            self.uri_opener._sleep_log, {bucket: False for bucket in ALL_BUCKETS}
        )

        server = LocalServer.serve_for(self, {"/": Reply(200, "ok")})
        ok_url = URL(server.url("/"))
        fail_url = URL(server.url("/fail-but-the-root-path-works"))
        server.routes[fail_url.get_path()] = Reply(drop=True)

        # Requests 1-6 fail: the error rate is above the acceptable 5%
        for _ in range(6):
            self.send(fail_url)

        for _ in range(4):
            self.send(ok_url)

        # The error rate is checked every five requests, the 11th request is
        # delayed for 6% (error rate) * SOCKET_ERROR_DELAY seconds
        self.assertGreaterEqual(self.send(ok_url), 6 * SOCKET_ERROR_DELAY)
        self.assertTrue(self.uri_opener._sleep_log[0])

        # The same error rate bucket doesn't trigger a new delay
        for _ in range(85):
            self.send(ok_url)

        self.assertTrue(self.uri_opener._sleep_log[0])
        self.assertFalse(self.uri_opener._sleep_log[10])

        # Four more errors move the error rate to the next bucket (10%) right
        # when the 100th request has been sent, which also clears the log
        for _ in range(4):
            self.send(fail_url)

        self.assertEqual(self.uri_opener.get_total_requests(), 100)
        self.assertGreaterEqual(self.send(ok_url), 10 * SOCKET_ERROR_DELAY)
        self.assertEqual(
            self.uri_opener._sleep_log, {bucket: False for bucket in ALL_BUCKETS}
        )

    def test_error_handling_disable_per_request(self):
        server = LocalServer.serve_for(self, {"/": SlowResponder(3)})
        url = URL(server.url())

        self.assertRaises(
            HTTPRequestException,
            self.uri_opener.GET,
            url,
            error_handling=False,
            timeout=1,
        )

        # No retries and the error was not logged
        self.assertEqual(len(server.requests), 1)
        self.assertEqual(self.uri_opener.get_error_rate(), 0)

    def test_exception_is_raised_always_after_stop(self):
        return_empty_daemon = UpperDaemon(EmptyTCPHandler)
        return_empty_daemon.start()
        return_empty_daemon.wait_for_start()

        url = URL(f"http://127.0.0.1:{return_empty_daemon.get_port()}/")
        http_exception_count = 0

        # Loop until we reach a must stop exception
        for _ in range(100):
            try:
                self.uri_opener.GET(url, cache=False)
            except HTTPRequestException:
                http_exception_count += 1
            except ScanMustStopByKnownReasonExc:
                break

        # We quickly reach this state, which is good since the server is down
        self.assertEqual(http_exception_count, 9)

        # After reaching this state we will always yield ScanMustStopByKnownReasonExc
        for _ in range(10):
            self.assertRaises(
                ScanMustStopByKnownReasonExc, self.uri_opener.GET, url, cache=False
            )

        # Clearing the state sends requests (and fails) again
        self.uri_opener.clear()
        self.assertRaises(HTTPRequestException, self.uri_opener.GET, url, cache=False)

    def test_reachable_root_path_keeps_the_scan_running(self):
        server = LocalServer.serve_for(
            self, {"/": Reply(200, "ok"), "/fail": Reply(drop=True)}
        )
        url = URL(server.url("/fail"))

        with self.assertLogs("w3af.core.data.url.extended_urllib", "DEBUG") as logs:
            for _ in range(15):
                self.assertRaises(HTTPRequestException, self.uri_opener.GET, url)

        root_checks = [r for r in server.requests if r.route == "/"]
        self.assertEqual(len(root_checks), 1)
        self.assertTrue(any("is reachable" in line for line in logs.output))
        self.assertIsNone(self.uri_opener._stop_exception)

    def test_root_path_check_interrupted_by_user_stop(self):
        failure = GatedFailure(gated_call=10)
        server = LocalServer.serve_for(self, {"/fail": failure})
        url = URL(server.url("/fail"))

        for _ in range(9):
            self.assertRaises(HTTPRequestException, self.uri_opener.GET, url)

        errors = []

        def send_tenth():
            try:
                self.uri_opener.GET(url)
            except ScanMustStopException as smse:
                errors.append(smse)

        tenth = threading.Thread(target=send_tenth, daemon=True)
        tenth.start()
        self.assertTrue(failure.received.wait(30))

        # The user stops the scan while the request is in flight, the check
        # which verifies if the root path is still reachable can't be sent
        self.uri_opener.stop()
        failure.release.set()
        tenth.join(30)

        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], ScanMustStopByKnownReasonExc)
        self.assertEqual([r.route for r in server.requests], ["/fail"] * 10)


class TestXUrllibErrorHandling(PluginTest):
    """
    We test that our xurllib can handle the case found at #8698 where many
    threads were sending requests to a URL which was timing out, thus reaching
    the MAX_ERROR_COUNT and stopping the whole scan.

    :see: https://github.com/andresriancho/w3af/issues/8698#issuecomment-77625343
    :see: https://github.com/andresriancho/w3af/issues/8698
    """

    _run_configs: ClassVar[dict] = {
        "cfg": {
            "target": None,
            "plugins": {
                "audit": (PluginConfig("lfi"),),
                "crawl": (
                    PluginConfig(
                        "web_spider", ("only_forward", True, PluginConfig.BOOL)
                    ),
                ),
            },
        }
    }

    def test_do_not_reach_must_stop_exception(self):
        # Configure low timeout to have faster test
        self.w3afcore.uri_opener.settings.set_configured_timeout(TIMEOUT_SECS)
        self.w3afcore.uri_opener.clear_timeout()
        self.addCleanup(self.w3afcore.uri_opener.settings.set_default_values)

        # Setup the server
        upper_daemon = ThreadingUpperDaemon(MultipleTimeoutsTCPHandler)
        upper_daemon.start()
        upper_daemon.wait_for_start()

        target_url = f"http://127.0.0.1:{upper_daemon.get_port()}/"

        cfg = self._run_configs["cfg"]

        with self.assertLogs("w3af.core.data.url.extended_urllib", "DEBUG") as logs:
            self._scan(target_url, cfg["plugins"])

        # The slow responses were logged as errors, but they didn't stop the scan
        self.assertTrue(
            any("ExtendedUrllib error rate is at" in line for line in logs.output)
        )
        self.assertIsNone(self.w3afcore.uri_opener._stop_exception)

        # Assert the vulnerability findings
        vulns = self.kb.get("lfi", "lfi")
        expected = [("5", "g")]

        self.assertAllVulnNamesEqual("Local file inclusion vulnerability", vulns)
        self.assertExpectedVulnsFound(expected, vulns)


class MultipleTimeoutsTCPHandler(socketserver.BaseRequestHandler):
    RESPONSE = (
        "HTTP/1.0 200 Ok\r\n"
        "Connection: Close\r\n"
        "Content-Length: %s\r\n"
        "Content-Type: text/html\r\n"
        "\r\n%s"
    )

    KA_RESPONSE = (
        "HTTP/1.0 200 Ok\r\n"
        "Connection: Keep-Alive\r\n"
        "Content-Length: %s\r\n"
        "Content-Type: text/html\r\n"
        "\r\n%s"
    )

    RESPONSE_404 = (
        "HTTP/1.0 404 Not Found\r\n"
        "Connection: Close\r\n"
        "Content-Length: %s\r\n"
        "Content-Type: text/html\r\n"
        "\r\n%s"
    )

    def reply(self, template, body):
        self.request.sendall((template % (len(body), body)).encode())

    def handle(self):
        fake_file = self.request.makefile("rb")
        header = fake_file.readline().decode("latin-1").strip()

        # Note the space after the =, these requests are to get the original
        # response and shouldn't be delayed
        if "?f= " in header or "?g= " in header:
            self.reply(self.RESPONSE, "Empty parameter")

        # Handling of the delayed+keep-alive responses
        elif "?f=" in header:
            time.sleep(TIMEOUT_SECS * 3)
            self.reply(self.KA_RESPONSE, "Slow response")

        # Handling of the vulnerability mock
        elif "etc%2Fpasswd" in header:
            self.reply(self.RESPONSE, f"Header {FILE_PATTERNS[0]} Footer")

        elif " / " in header:
            # Handling the index
            self.reply(self.RESPONSE, '<a href="/1?f=">1</a><a href="/5?g=">5</a>')
        else:
            self.reply(self.RESPONSE_404, "Not found")
