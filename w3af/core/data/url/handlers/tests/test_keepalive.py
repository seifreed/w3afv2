"""
test_keepalive.py

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

import os
import socketserver
import time
import unittest
import urllib.request

import psutil

from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.url.handlers.keepalive import (
    ConnectionManager,
    HTTPHandler,
    HTTPSHandler,
    URLTimeoutError,
)
from w3af.core.data.url.http_request import HTTPRequest
from w3af.core.data.url.tests.helpers.route_server import (
    RecordedRequest,
    Response,
    RouteServer,
)
from w3af.core.data.url.tests.helpers.upper_daemon import UpperDaemon

UNUSED_URL = "http://127.0.0.1:8080/"
SLOW_RESPONSE_SECONDS = 2
REQUEST_TIMEOUT_SECONDS = 0.3


def slow_response(_request: RecordedRequest) -> Response:
    time.sleep(SLOW_RESPONSE_SECONDS)
    return Response(body="Too late")


class CloseAfterResponseHandler(socketserver.BaseRequestHandler):
    """
    Answers like a keep-alive server but closes the socket right away, which
    leaves the client side socket in CLOSE_WAIT.
    """

    def handle(self):
        self.request.recv(1024)
        self.request.sendall(
            b"HTTP/1.1 200 Ok\r\n"
            b"Content-Type: text/plain\r\n"
            b"Content-Length: 3\r\n"
            b"\r\nabc"
        )


def connections_to_port(port):
    return [
        conn
        for conn in psutil.Process(os.getpid()).net_connections(kind="tcp")
        if conn.raddr and conn.raddr.port == port
    ]


class TestKeepalive(unittest.TestCase):

    def setUp(self):
        self.server = RouteServer()
        self.server.add(
            "GET", "/close", Response(body="bye", headers=[("Connection", "close")])
        )
        self.server.add("GET", "/keep", Response(body="hello"))
        self.server.add("GET", "/slow", slow_response)
        self.server.start()

    def tearDown(self):
        self.server.stop()

    def test_get_and_remove_conn(self):
        """
        Each requested connection must be closed by calling 'remove_connection'
        when the server doesn't support persistent HTTP Connections
        """
        handler = HTTPHandler()
        opener = urllib.request.build_opener(handler)
        request = HTTPRequest(URL(self.server.url("/close")))

        response = opener.open(request)

        self.assertEqual(response.read(), b"bye")
        self.assertTrue(response.will_close)
        self.assertEqual(handler._cm.get_connections_total(), 0)

    def test_keep_alive_conn_is_freed(self):
        handler = HTTPHandler()
        opener = urllib.request.build_opener(handler)
        request = HTTPRequest(URL(self.server.url("/keep")))

        response = opener.open(request)
        response.read()

        self.assertFalse(response.will_close)
        self.assertEqual(len(handler._cm._used_conns), 0)
        self.assertEqual(len(handler._cm._free_conns), 1)
        handler.close_all()

    def test_timeout(self):
        """
        Ensure that kah raises 'URLTimeoutError' when timeouts occur and the
        connection that timed out is removed from the pool.
        """
        handler = HTTPHandler()
        opener = urllib.request.build_opener(handler)
        url = URL(self.server.url("/slow"))

        # We raise URLTimeoutError each time the connection timeouts, the
        # keepalive handler doesn't take any decisions like
        # ScanMustStopByKnownReasonExc, which is the job of the extended urllib
        for _ in range(2):
            self.assertRaises(
                URLTimeoutError,
                opener.open,
                HTTPRequest(url),
                None,
                REQUEST_TIMEOUT_SECONDS,
            )
            self.assertEqual(handler._cm.get_connections_total(), 0)

        self.assertEqual(len(self.server.requests), 2)

    def test_free_connection(self):
        """
        Ensure that conns are returned back to the pool when requests are
        closed.
        """
        handler = HTTPHandler()
        request = HTTPRequest(URL(UNUSED_URL))
        conn = handler._cm.get_available_connection(request, handler.get_connection)

        handler._request_closed(conn)

        self.assertIn(conn, handler._cm._free_conns)
        self.assertNotIn(conn, handler._cm._used_conns)

    def test_single_conn_mgr(self):
        """
        We want to use different instances of the ConnectionManager for HTTP
        and HTTPS.
        """
        conn_mgr_http = HTTPHandler()._cm
        conn_mgr_https = HTTPSHandler(":")._cm

        self.assertIsNot(conn_mgr_http, conn_mgr_https)

    def test_close_all_established_sockets(self):
        self.close_all_sockets(self.server.url("/keep"), self.server.port)

    def test_close_all_close_wait_sockets(self):
        daemon = UpperDaemon(CloseAfterResponseHandler)
        daemon.start()
        daemon.wait_for_start()
        port = daemon.get_port()

        # Give the socket time to move to close_wait
        self.close_all_sockets(f"http://127.0.0.1:{port}/", port, wait=1)

    def close_all_sockets(self, url, port, wait=0):
        keep_alive_http = HTTPHandler()

        uri_opener = urllib.request.build_opener(keep_alive_http)

        request = HTTPRequest(URL(url))
        response = uri_opener.open(request)
        response.read()

        time.sleep(wait)

        connections_before = connections_to_port(port)

        keep_alive_http.close_all()

        time.sleep(1)
        connections_after = connections_to_port(port)

        self.assertLess(len(connections_after), len(connections_before))


class TestConnectionMgr(unittest.TestCase):

    def setUp(self):
        self.cm = ConnectionManager()
        self.conn_factory = HTTPHandler().get_connection
        self.request = HTTPRequest(URL(UNUSED_URL))

    def test_get_available_conn_reuse(self):
        # We don't need a new HTTPConnection for each request
        self.request.set_new_connection(False)

        self.cm.MAX_CONNECTIONS = 1  # Only a single connection
        self.assertEqual(0, len(self.cm._used_conns))
        self.assertEqual(0, len(self.cm._free_conns))

        # Get connection
        conn_1 = self.cm.get_available_connection(self.request, self.conn_factory)
        self.assertEqual(1, len(self.cm._used_conns))
        self.assertEqual(0, len(self.cm._free_conns))

        # Return it to the pool
        self.cm.free_connection(conn_1)
        self.assertEqual(0, len(self.cm._used_conns))
        self.assertEqual(1, len(self.cm._free_conns))

        # Ask for a conn again, since we don't need a new connection, it should
        # return one from the pool
        conn_2 = self.cm.get_available_connection(self.request, self.conn_factory)
        self.assertIs(conn_2, conn_1)

    def test_get_available_conn_new_connection_requested(self):
        # We want a new HTTPConnection for each request
        self.request.set_new_connection(True)

        self.cm.MAX_CONNECTIONS = 2
        self.assertEqual(0, len(self.cm._used_conns))
        self.assertEqual(0, len(self.cm._free_conns))

        # Get connection
        conn_1 = self.cm.get_available_connection(self.request, self.conn_factory)
        self.assertEqual(1, len(self.cm._used_conns))
        self.assertEqual(0, len(self.cm._free_conns))

        # Return it to the pool
        self.cm.free_connection(conn_1)
        self.assertEqual(0, len(self.cm._used_conns))
        self.assertEqual(1, len(self.cm._free_conns))

        # Ask for another connection, it should return a new one
        conn_2 = self.cm.get_available_connection(self.request, self.conn_factory)
        self.assertIsNot(conn_1, conn_2)

    def test_replace_conn(self):
        bad_conn = self.conn_factory(self.request)
        self.cm.replace_connection(bad_conn, self.request, self.conn_factory)
        bad_conn = self.cm.get_available_connection(self.request, self.conn_factory)
        old_len = self.cm.get_connections_total()

        # Replace bad with a new one
        new_conn = self.cm.replace_connection(bad_conn, self.request, self.conn_factory)

        # Must be different conn objects
        self.assertNotEqual(bad_conn, new_conn)

        # The len must be the same
        self.assertEqual(self.cm.get_connections_total(), old_len)

    def test_remove_conn(self):
        self.assertEqual(self.cm.get_connections_total(), 0)

        conn = self.cm.get_available_connection(self.request, self.conn_factory)
        self.assertEqual(self.cm.get_connections_total(), 1)

        self.cm.remove_connection(conn, reason="unittest")

        self.assertEqual(self.cm.get_connections_total(), 0)
