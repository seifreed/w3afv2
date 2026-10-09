"""
test_xurllib_error_handling.py

Copyright 2015 Andres Riancho

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

import w3af.core.controllers.output_manager as om
from w3af.core.controllers.plugins.output_plugin import OutputPlugin
from w3af.core.data.constants import severity
from w3af.core.data.constants.file_patterns import FILE_PATTERNS
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.url.constants import ACCEPTABLE_ERROR_RATE, SOCKET_ERROR_DELAY
from w3af.core.data.url.exceptions import HTTPRequestException
from w3af.core.data.url.extended_urllib import ExtendedUrllib
from w3af.core.data.url.tests.helpers.sleep_recorder import SleepRecorder
from w3af.core.data.url.tests.helpers.upper_daemon import (
    ThreadingUpperDaemon,
    UpperDaemon,
)
from w3af.core.data.url.tests.test_xurllib import EmptyTCPHandler
from w3af.core.exceptions import (
    ScanMustStopByKnownReasonExc,
)
from w3af.plugins.tests.helper import PluginConfig, PluginTest

TIMEOUT_SECS = 1


class RootOkOtherPathsEmptyTCPHandler(socketserver.BaseRequestHandler):
    """
    The server root path is reachable, any other path closes the connection
    without sending an HTTP response.
    """

    def handle(self):
        request_line = self.request.makefile("rb").readline()
        if b" / " in request_line:
            self.request.sendall(
                b"HTTP/1.0 200 Ok\r\n"
                b"Connection: Close\r\n"
                b"Content-Length: 2\r\n"
                b"\r\nOk"
            )


class CountingTimeoutTCPHandler(socketserver.BaseRequestHandler):
    """
    Counts the received connections and never answers in time.
    """

    connections = 0
    lock = threading.Lock()

    def handle(self):
        with CountingTimeoutTCPHandler.lock:
            CountingTimeoutTCPHandler.connections += 1
        self.request.recv(1024)
        time.sleep(TIMEOUT_SECS * 3)


@pytest.mark.smoke
class TestXUrllibDelayOnError(unittest.TestCase):

    def setUp(self):
        self.error_pauses = SleepRecorder()
        self.uri_opener = ExtendedUrllib(sleep=self.error_pauses)

    def tearDown(self):
        self.uri_opener.end()

    def test_increasing_delay_on_errors(self):
        expected_log = {
            0: False,
            70: False,
            40: False,
            10: False,
            80: False,
            50: False,
            20: False,
            90: False,
            60: False,
            30: False,
            100: False,
        }
        self.assertEqual(self.uri_opener._sleep_log, expected_log)

        # The root path is reachable, which keeps the scan going (see
        # _should_stop_scan) while all the requests to /error fail
        daemon = ThreadingUpperDaemon(RootOkOtherPathsEmptyTCPHandler)
        daemon.start()
        daemon.wait_for_start()

        port = daemon.get_port()

        # No retries means that the test is easier to read/understand
        self.uri_opener.settings.set_max_http_retries(0)

        url = URL(f"http://127.0.0.1:{port}/error")
        http_exception_count = 0
        loops = 100

        # Now check the delays
        for i in range(loops):
            try:
                self.uri_opener.GET(url, cache=False)
            except HTTPRequestException:
                http_exception_count += 1
            else:
                self.assertTrue(False, "Expecting HTTPRequestException")

        self.assertEqual(loops - 1, i)

        # Note that the timeouts are increasing based on the error rate and
        # SOCKET_ERROR_DELAY
        delays = self.error_pauses.delays
        self.assertGreaterEqual(len(delays), 9)
        self.assertEqual(delays, sorted(delays))
        for delay in delays:
            error_rate = delay / SOCKET_ERROR_DELAY
            self.assertGreater(error_rate, ACCEPTABLE_ERROR_RATE)

        self.assertEqual(http_exception_count, 100)
        self.assertEqual(delays[0], SOCKET_ERROR_DELAY * 10)

        # The sleep log is cleared every 100 requests: we slept at a 10% error
        # rate but that entry was reset, while the latest pause is recorded
        sleep_log = self.uri_opener._sleep_log
        self.assertFalse(sleep_log[10])
        self.assertTrue(sleep_log[90])

    def test_error_handling_disable_per_request(self):
        CountingTimeoutTCPHandler.connections = 0
        upper_daemon = ThreadingUpperDaemon(CountingTimeoutTCPHandler)
        upper_daemon.start()
        upper_daemon.wait_for_start()

        port = upper_daemon.get_port()

        self.uri_opener.settings.set_configured_timeout(TIMEOUT_SECS)
        self.uri_opener.clear_timeout()

        url = URL(f"http://127.0.0.1:{port}/")

        try:
            self.uri_opener.GET(url, error_handling=False)
        except HTTPRequestException:
            # Without error handling the request is not retried
            self.assertEqual(CountingTimeoutTCPHandler.connections, 1)
        else:
            self.assertTrue(False, "Exception not raised")

        self.uri_opener.settings.set_default_values()

    def test_exception_is_raised_always_after_stop(self):
        return_empty_daemon = UpperDaemon(EmptyTCPHandler)
        return_empty_daemon.start()
        return_empty_daemon.wait_for_start()

        port = return_empty_daemon.get_port()

        # No retries means that the test is easier to read/understand
        self.uri_opener.settings.set_max_http_retries(0)

        url = URL(f"http://127.0.0.1:{port}/")
        http_exception_count = 0
        loops = 100

        # Loop until we reach a must stop exception
        for i in range(loops):
            try:
                self.uri_opener.GET(url, cache=False)
            except HTTPRequestException:
                http_exception_count += 1
            except ScanMustStopByKnownReasonExc:
                break
            else:
                self.assertTrue(False, "Expecting an exception")

        # We quickly reach this state, which is good since the server is down
        self.assertEqual(http_exception_count, 9)

        # After reaching this state we will always yield ScanMustStopByKnownReasonExc
        for i in range(loops):
            self.assertRaises(
                ScanMustStopByKnownReasonExc, self.uri_opener.GET, url, cache=False
            )

        # Confirm that the stored stop exception is the one being raised
        with self.assertRaises(ScanMustStopByKnownReasonExc) as stop:
            self.uri_opener.GET(url, cache=False)
        self.assertIs(stop.exception, self.uri_opener._stop_exception)


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

    def scan_with_output_plugin(self, target_url, plugins, output_plugin):
        self._set_target(target_url, verify_targets=True)
        self._set_enabled_plugins(plugins)
        self._set_uri_opener_settings()

        self.w3afcore.plugins.init_plugins()
        om.manager.set_output_plugin_inst(output_plugin)
        self.w3afcore.verify_environment()
        self.w3afcore.start()

        caught_exceptions = self.w3afcore.exception_handler.get_all_exceptions()
        tracebacks = [e.get_details() for e in caught_exceptions]
        self.assertEqual(len(caught_exceptions), 0, tracebacks)

    def test_do_not_reach_must_stop_exception(self):
        # Configure low timeout to have faster test
        self.w3afcore.uri_opener.settings.set_configured_timeout(TIMEOUT_SECS)
        self.w3afcore.uri_opener.clear_timeout()

        # Setup the server
        upper_daemon = ThreadingUpperDaemon(MultipleTimeoutsTCPHandler)
        upper_daemon.start()
        upper_daemon.wait_for_start()

        port = upper_daemon.get_port()
        target_url = f"http://127.0.0.1:{port}/"

        # Run the scan
        output = RecordingOutputPlugin()
        self.scan_with_output_plugin(
            target_url, self._run_configs["cfg"]["plugins"], output
        )

        # This one should appear each time
        self.assertIn("ExtendedUrllib error rate is at 10%", output.messages["debug"])
        self.assertEqual(len(output.messages["vulnerability"]), 1)

        # Restore the defaults
        self.w3afcore.uri_opener.settings.set_default_values()

        # The scan status was cleared and no exceptions were stored
        self.assertIsNone(self.w3afcore.uri_opener._stop_exception)
        self.assertEqual(self.w3afcore.uri_opener.get_total_requests(), 0)

        # Assert the vulnerability findings
        vulns = self.kb.get("lfi", "lfi")

        # Verify the specifics about the vulnerabilities
        expected = [("5", "g")]

        self.assertAllVulnNamesEqual("Local file inclusion vulnerability", vulns)
        self.assertExpectedVulnsFound(expected, vulns)


class RecordingOutputPlugin(OutputPlugin):
    """
    Output plugin that keeps every message it receives in memory.
    """

    def __init__(self):
        super().__init__()
        self.messages = {
            "debug": [],
            "information": [],
            "error": [],
            "vulnerability": [],
            "console": [],
        }

    def debug(self, message, new_line=True):
        self.messages["debug"].append(message)

    def information(self, message, new_line=True):
        self.messages["information"].append(message)

    def error(self, message, new_line=True):
        self.messages["error"].append(message)

    def vulnerability(self, message, new_line=True, severity=severity.MEDIUM):
        self.messages["vulnerability"].append(message)

    def console(self, message, new_line=True):
        self.messages["console"].append(message)


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

    def handle(self):
        fake_file = self.request.makefile()
        header = fake_file.readline().strip()

        # Note the space after the =, these requests are to get the original
        # response and shouldn't be delayed
        if "?f= " in header or "?g= " in header:
            body = "Empty parameter"
            self.request.sendall((self.RESPONSE % (len(body), body)).encode())

        # Handling of the delayed+keep-alive responses
        elif "?f=" in header:
            time.sleep(TIMEOUT_SECS * 3)
            body = "Slow response"
            self.request.sendall((self.KA_RESPONSE % (len(body), body)).encode())

        # Handling of the vulnerable response
        elif "etc%2Fpasswd" in header:
            body = f"Header {FILE_PATTERNS[0]} Footer"
            self.request.sendall((self.RESPONSE % (len(body), body)).encode())

        elif " / " in header:
            # Handling the index
            links = (
                '<a href="/1?f=">1</a>'
                #'<a href="/2?f=">2</a>'
                #'<a href="/3?f=">3</a>'
                #'<a href="/4?f=">4</a>'
                '<a href="/5?g=">5</a>'
            )
            self.request.sendall((self.RESPONSE % (len(links), links)).encode())
        else:
            body = "Not found"
            self.request.sendall((self.RESPONSE_404 % (len(body), body)).encode())
