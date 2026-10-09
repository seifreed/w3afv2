"""
test_xurllib_timeout.py

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

import time
import unittest

import pytest

from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.url.constants import (
    DEFAULT_TIMEOUT,
    MAX_ERROR_COUNT,
    MIN_TIMEOUT,
    TIMEOUT_ADJUST_LIMIT,
    TIMEOUT_MULT_CONST,
    TIMEOUT_UPDATE_ELAPSED_MIN,
)
from w3af.core.data.url.exceptions import HTTPRequestException
from w3af.core.data.url.extended_urllib import ExtendedUrllib
from w3af.core.data.url.handlers.keepalive.connection_manager import ConnectionManager
from w3af.core.data.url.tests.helpers.local_server import LocalServer, Reply
from w3af.core.data.url.tests.helpers.raw_handlers import TimeoutTCPHandler
from w3af.core.data.url.tests.helpers.ssl_daemon import RawSSLDaemon
from w3af.core.data.url.tests.helpers.upper_daemon import (
    ThreadingUpperDaemon,
    UpperDaemon,
)
from w3af.core.exceptions import ScanMustStopException

LOGGER_NAME = "w3af.core.data.url.extended_urllib"


class DelayedReply:
    def __init__(self, regular_sleep=0.1, long_sleep=7.0):
        self.regular_sleep = regular_sleep
        self.long_sleep = long_sleep

    def __call__(self, request):
        time.sleep(self.regular_sleep)

        # When /timeout is requested, we sleep some extra seconds
        if request.route == "/timeout":
            time.sleep(self.long_sleep)

        return Reply(200, "abc")


@pytest.mark.smoke
class TestXUrllibTimeout(unittest.TestCase):

    def setUp(self):
        self.uri_opener = ExtendedUrllib()
        self.addCleanup(self.uri_opener.end)
        self.addCleanup(self.uri_opener.settings.set_default_values)

    def start_timeout_daemon(self, daemon_klass=UpperDaemon):
        daemon = daemon_klass(TimeoutTCPHandler)
        daemon.start()
        daemon.wait_for_start()
        return daemon.get_port()

    def test_timeout(self):
        url = URL(f"http://127.0.0.1:{self.start_timeout_daemon()}/")

        self.uri_opener.settings.set_max_http_retries(0)
        self.uri_opener.settings.set_configured_timeout(0.5)
        self.uri_opener.clear_timeout()

        with self.assertRaises(HTTPRequestException) as raised:
            self.uri_opener.GET(url)

        self.assertEqual(str(raised.exception), "HTTP timeout error")

    def test_timeout_ssl(self):
        port = self.start_timeout_daemon(RawSSLDaemon)
        url = URL(f"https://127.0.0.1:{port}/")

        self.uri_opener.settings.set_max_http_retries(0)
        self.uri_opener.settings.set_configured_timeout(1)
        self.uri_opener.clear_timeout()

        self.assertRaises(HTTPRequestException, self.uri_opener.GET, url)

    def test_timeout_many(self):
        # Each connection is handled in its own thread, a single threaded
        # server would fill the listen backlog and reset the connections
        port = self.start_timeout_daemon(ThreadingUpperDaemon)
        url = URL(f"http://127.0.0.1:{port}/")

        self.uri_opener.settings.set_configured_timeout(0.5)
        self.uri_opener.clear_timeout()

        http_request_e = 0
        scan_stop_e = 0

        for _ in range(MAX_ERROR_COUNT):
            try:
                self.uri_opener.GET(url)
            except HTTPRequestException as hre:
                http_request_e += 1
                self.assertEqual(str(hre), "HTTP timeout error")
            except ScanMustStopException:
                scan_stop_e += 1
                break

        # Each GET is sent twice (MAX_HTTP_RETRIES), after ten consecutive
        # errors the root path is checked and found unreachable
        self.assertEqual(http_request_e, 4)
        self.assertEqual(scan_stop_e, 1)

    def test_timeout_auto_adjust(self):
        server = LocalServer.serve_for(self, {"/": DelayedReply()})

        # Enable timeout auto-adjust
        self.uri_opener.settings.set_configured_timeout(0)
        self.uri_opener.clear_timeout()

        # Make sure we start from the desired timeout value
        self.assertEqual(self.uri_opener.get_timeout("127.0.0.1"), DEFAULT_TIMEOUT)

        url = URL(server.url())

        self.uri_opener.GET(url)
        time.sleep(TIMEOUT_UPDATE_ELAPSED_MIN + 1)

        with self.assertLogs(LOGGER_NAME, "DEBUG") as logs:
            for _ in range(TIMEOUT_ADJUST_LIMIT):
                self.uri_opener.GET(url)

        updates = [line for line in logs.output if "Updating socket timeout" in line]
        self.assertEqual(len(updates), 1)

        rtt = self.uri_opener.get_average_rtt()[0]
        expected_timeout = max(MIN_TIMEOUT, TIMEOUT_MULT_CONST * rtt)
        self.assertAlmostEqual(
            self.uri_opener.get_timeout("127.0.0.1"), expected_timeout, delta=rtt
        )
        self.assertLess(self.uri_opener.get_timeout("127.0.0.1"), DEFAULT_TIMEOUT)

    def test_auto_adjust_needs_samples_for_the_host(self):
        server = LocalServer.serve_for(self, {"/": Reply(200, "abc")})

        self.uri_opener.settings.set_configured_timeout(0)
        self.uri_opener.clear_timeout()

        # The first TIMEOUT_ADJUST_LIMIT requests are sent to 127.0.0.1, the
        # adjustment is triggered by a request to localhost, which has no RTT
        # samples yet
        for _ in range(TIMEOUT_ADJUST_LIMIT):
            self.uri_opener.GET(URL(server.url()))

        with self.assertLogs(LOGGER_NAME, "DEBUG") as logs:
            self.uri_opener.GET(URL(server.url(host="localhost")))

        self.assertTrue(
            any("Not enough samples collected (0)" in line for line in logs.output)
        )
        self.assertEqual(self.uri_opener.get_timeout("localhost"), DEFAULT_TIMEOUT)
        self.assertEqual(self.uri_opener.get_average_rtt(host="w3af.org"), (None, 0))

    def test_timeout_parameter_overrides_global_timeout(self):
        delayed = DelayedReply()
        server = LocalServer.serve_for(self, {"/": delayed, "/timeout": delayed})

        # Enable timeout auto-adjust
        self.uri_opener.settings.set_configured_timeout(0)
        self.uri_opener.clear_timeout()

        # Make sure we start from the desired timeout value
        self.assertEqual(self.uri_opener.get_timeout("127.0.0.1"), DEFAULT_TIMEOUT)

        url = URL(server.url())

        self.uri_opener.GET(url)
        time.sleep(TIMEOUT_UPDATE_ELAPSED_MIN + 1)

        for _ in range(TIMEOUT_ADJUST_LIMIT * 3):
            self.uri_opener.GET(url)

        # These make sure that the HTTP connection pool is full, this is
        # required because we want to check if the timeout applies to
        # existing connections, not new ones
        for _ in range(ConnectionManager.MAX_CONNECTIONS):
            self.uri_opener.GET(url)

        # Make sure we reached the desired timeout after our HTTP
        # requests to the test server
        self.assertEqual(self.uri_opener.get_timeout("127.0.0.1"), MIN_TIMEOUT)

        timeout_url = URL(server.url("/timeout"))

        # And now the real test, this one makes sure that the timeout
        # parameter sent to GET overrides the configured value
        response = self.uri_opener.GET(timeout_url, timeout=8.0)
        self.assertEqual(response.get_code(), 200)

        self.assertEqual(self.uri_opener.get_timeout("127.0.0.1"), MIN_TIMEOUT)

        # When timeout is not specified and the server returns in more
        # than the expected time, an exception is raised
        self.assertRaises(HTTPRequestException, self.uri_opener.GET, timeout_url)
