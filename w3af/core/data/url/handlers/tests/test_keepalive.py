"""
test_keepalive.py

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

import http.client
import os
import socket
import threading
import time
import unittest

import OpenSSL

from w3af.core.data.kb.config import Config
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.url.director import CustomOpenerDirector, build_opener
from w3af.core.data.url.exceptions import ConnectionPoolException, HTTPRequestException
from w3af.core.data.url.handlers.keepalive import (
    ConnectionManager,
    HTTPHandler,
    HTTPResponse,
    HTTPSHandler,
    KeepAliveHandler,
    URLTimeoutError,
    connection_manager,
    utils,
)
from w3af.core.data.url.handlers.keepalive.connections import (
    HTTPConnection,
    HTTPSConnection,
    ProxyHTTPConnection,
    create_connection,
)
from w3af.core.data.url.http_request import HTTPRequest
from w3af.core.data.url.openssl_wrapper.ssl_wrapper import SSLSocket
from w3af.core.data.url.tests.helpers.certificates import server_tls_context
from w3af.core.data.url.tests.helpers.raw_server import (
    ConnectProxy,
    RawServer,
    read_http_head,
)
from w3af.core.data.url.tests.helpers.route_server import (
    LOCALHOST,
    Response,
    RouteServer,
)
from w3af.core.exceptions import BaseFrameworkException


def closed_port():
    with socket.socket() as sock:
        sock.bind((LOCALHOST, 0))
        return sock.getsockname()[1]


def request(url, timeout=5, **kwargs):
    return HTTPRequest(URL(url), timeout=timeout, **kwargs)


def raw(response_bytes):
    return Response(raw=response_bytes)


def sequence(*replies):
    """
    :return: A route answering each request with the next reply
    """
    pending = list(replies)
    return lambda _request: pending.pop(0)


class OpenerTestCase(unittest.TestCase):
    def setUp(self):
        self.use_handler(HTTPHandler(cf))

    def use_handler(self, handler):
        # The pool only reuses connections once it is full, a single
        # connection pool makes every request after the first one reuse it
        self.handler = handler
        self.handler._cm.MAX_CONNECTIONS = 1
        self.opener = build_opener(CustomOpenerDirector, [self.handler])

    def serve(self, routes, **kwargs):
        server = RouteServer(routes, **kwargs).start()
        self.addCleanup(server.stop)
        return server

    def total_connections(self, handler=None):
        return (handler or self.handler)._cm.get_connections_total()


class TestHTTPKeepAlive(OpenerTestCase):
    def test_persistent_connection_is_reused(self):
        server = self.serve({"/": Response(body="hello")})

        first = self.opener.open(request(server.url()))
        second = self.opener.open(request(server.url()))

        self.assertIs(first._connection, second._connection)
        self.assertEqual(first._connection.req_count, 2)
        self.assertEqual(self.total_connections(), 1)
        self.assertEqual(second.read(), b"hello")
        self.assertEqual(second.read(), b"hello")
        self.assertEqual(second.read(2), b"he")
        self.assertEqual(second.code, 200)
        self.assertEqual(second.msg, "OK")
        self.assertEqual(second.geturl(), server.url())
        self.assertEqual(second.info()["Content-Length"], "5")
        self.assertGreaterEqual(second.get_wait_time(), 0)

        second.encoding = "utf-8"
        self.assertEqual(second.encoding, "utf-8")

        self.handler.close_all()
        self.assertEqual(self.total_connections(), 0)

    def test_connection_close_removes_the_connection(self):
        server = self.serve(
            {"/": Response(body="bye", headers=[("Connection", "close")])}
        )

        response = self.opener.open(request(server.url()))

        self.assertEqual(response.read(), b"bye")
        self.assertEqual(self.total_connections(), 0)

    def test_new_connection_requests_are_not_pooled(self):
        server = self.serve({"/": Response(body="fresh")})

        self.opener.open(request(server.url(), new_connection=True))

        self.assertEqual(self.total_connections(), 0)

    def test_connection_closed_by_the_server_is_replaced(self):
        server = self.serve(
            {"/": sequence(Response(body="first", close=True), Response(body="second"))}
        )

        first = self.opener.open(request(server.url()))
        first_connection = first._connection
        second = self.opener.open(request(server.url()))

        self.assertEqual(second.read(), b"second")
        self.assertIsNot(second._connection, first_connection)
        self.assertEqual(self.total_connections(), 1)

    def test_http_09_answer_on_a_reused_connection(self):
        server = self.serve(
            {
                "/": sequence(
                    Response(body="first"),
                    raw(b"HTTP/0.9 200 OK\r\n\r\nancient"),
                    Response(body="third"),
                )
            }
        )

        self.opener.open(request(server.url()))
        response = self.opener.open(request(server.url()))

        self.assertEqual(response.read(), b"third")

    def test_http_09_answer_on_a_fresh_connection(self):
        server = self.serve({"/": raw(b"HTTP/0.9 200 OK\r\nancient")})

        response = self.opener.open(request(server.url()))

        self.assertEqual(response.read(), b"ancient")
        self.assertEqual(self.total_connections(), 0)

    def test_unknown_protocol_version(self):
        server = self.serve({"/": raw(b"HTTP/2.0 200 OK\r\n\r\n")})

        with self.assertRaises(http.client.UnknownProtocol):
            self.opener.open(request(server.url()))
        self.assertEqual(self.total_connections(), 0)

    def test_100_continue_is_skipped(self):
        server = self.serve(
            {
                "/": raw(
                    b"HTTP/1.1 100 Continue\r\nX-Info: wait\r\n\r\n"
                    b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok"
                )
            }
        )

        response = self.opener.open(request(server.url()))

        self.assertEqual(response.read(), b"ok")

    def test_100_continue_with_a_huge_header(self):
        line = b"X-Huge: " + b"a" * (http.client._MAXLINE + 1) + b"\r\n"
        server = self.serve({"/": raw(b"HTTP/1.1 100 Continue\r\n" + line + b"\r\n")})

        with self.assertRaises(http.client.LineTooLong):
            self.opener.open(request(server.url()))

    def test_incomplete_body(self):
        server = self.serve(
            {"/": raw(b"HTTP/1.1 200 OK\r\nContent-Length: 10\r\n\r\nabc")}
        )

        with self.assertRaises(http.client.IncompleteRead):
            self.opener.open(request(server.url()))
        self.assertEqual(self.total_connections(), 0)

    def test_timeout(self):
        def never_answer(sock):
            read_http_head(sock)
            time.sleep(2)

        with RawServer(never_answer) as server:
            url = f"http://{LOCALHOST}:{server.port}/"
            with self.assertRaises(URLTimeoutError):
                self.opener.open(request(url, timeout=0.3))

        self.assertEqual(self.total_connections(), 0)

    def test_connection_refused(self):
        url = f"http://{LOCALHOST}:{closed_port()}/"

        with self.assertRaises(ConnectionRefusedError):
            self.opener.open(request(url))
        self.assertEqual(self.total_connections(), 0)

    def test_request_without_host(self):
        req = request("http://w3af.org/")
        req.host = ""

        with self.assertRaisesRegex(OSError, "no host given"):
            self.handler.do_open_keepalive(req)

    def test_post_data_headers(self):
        server = self.serve({"/": Response(body="ok")})

        self.opener.open(request(server.url(), data="a=1"))
        self.opener.open(
            request(
                server.url(),
                data=b"{}",
                headers={"Content-Type": "application/json", "Content-Length": "2"},
            )
        )

        default, explicit = server.requests
        self.assertEqual(default.body, b"a=1")
        self.assertEqual(
            default.headers["Content-type"], "application/x-www-form-urlencoded"
        )
        self.assertEqual(default.headers["Content-length"], "3")
        self.assertEqual(default.headers["Connection"], "keep-alive")
        self.assertEqual(explicit.headers["Content-Type"], "application/json")

    def test_headers_which_http_client_rejects_are_rfc2047_encoded(self):
        server = self.serve({"/": Response(body="ok")})
        req = request(server.url())
        req.add_unredirected_header("Bad:name", "value")
        req.add_unredirected_header("X-multi-line", "one\ntwo")
        req.headers[None] = "ignored"
        req.headers["X-empty"] = None

        self.opener.open(req)

        received = server.requests[0].headers
        self.assertEqual(received["=?utf-8?b?QmFkOm5hbWU=?="], "value")
        self.assertEqual(received["X-multi-line"], "=?utf-8?b?b25lCnR3bw==?=")
        self.assertEqual(received["X-empty"], "")

    def test_head_responses_have_no_body(self):
        server = self.serve({"/": Response(body="not sent")})

        response = self.opener.open(request(server.url(), method="HEAD"))

        self.assertEqual(response.read(), b"")
        self.assertEqual(self.total_connections(), 1)

    def test_bodies_bigger_than_max_file_size_are_dropped(self):
        previous = cf.get("max_file_size")
        self.addCleanup(cf.save, "max_file_size", previous)
        cf.save("max_file_size", 5)
        server = self.serve({"/": Response(body="x" * 100)})

        response = self.opener.open(request(server.url()))

        self.assertEqual(response.read(), b"")
        self.assertEqual(response.code, 200)
        self.assertEqual(response.status, 204)

    def test_reused_connection_gets_the_request_timeout(self):
        server = self.serve({"/": Response(body="ok")})

        first = self.opener.open(request(server.url()))
        self.opener.open(request(server.url(), timeout=socket._GLOBAL_DEFAULT_TIMEOUT))
        self.assertEqual(
            first._connection.sock.gettimeout(), socket.getdefaulttimeout()
        )

        self.opener.open(request(server.url(), timeout=3))
        self.assertEqual(first._connection.sock.gettimeout(), 3)

    def test_url_timeout_error_message(self):
        previous = socket.getdefaulttimeout()
        self.addCleanup(socket.setdefaulttimeout, previous)

        socket.setdefaulttimeout(7)
        self.assertEqual(str(URLTimeoutError()), "HTTP timeout error after 7.0 seconds")

        socket.setdefaulttimeout(None)
        self.assertEqual(str(URLTimeoutError()), "HTTP timeout error")

    def test_base_handler_has_no_connection_factory(self):
        self.assertRaises(NotImplementedError, KeepAliveHandler().get_connection, None)


class TestHTTPSKeepAlive(OpenerTestCase):
    def setUp(self):
        self.use_handler(HTTPSHandler(":", cf))

    def test_persistent_https_connection(self):
        server = self.serve(
            {"/": Response(body="secure")}, tls_context=server_tls_context()
        )

        first = self.opener.open(request(server.url()))
        second = self.opener.open(request(server.url()))

        self.assertIsInstance(first._connection, HTTPSConnection)
        self.assertIs(first._connection, second._connection)
        self.assertEqual(second.read(), b"secure")
        self.handler.close_all()

    def test_tls_errors_on_a_reused_connection(self):
        context = server_tls_context()

        def corrupt_after_first_answer(sock):
            with context.wrap_socket(sock, server_side=True) as tls:
                read_http_head(tls)
                tls.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok")
                time.sleep(0.2)
                with socket.socket(fileno=os.dup(tls.fileno())) as plain:
                    plain.sendall(b"\x17\x03\x03\x00\x05hello")
                time.sleep(1)

        with RawServer(corrupt_after_first_answer) as server:
            url = f"https://{LOCALHOST}:{server.port}/"
            self.opener.open(request(url))
            time.sleep(0.4)
            with self.assertRaises(OpenSSL.SSL.Error):
                self.opener.open(request(url))

        self.assertEqual(self.total_connections(), 0)

    def test_https_to_a_plain_http_server(self):
        server = self.serve({"/": Response(body="plain")})
        url = f"https://{server.netloc}/"

        with self.assertRaises(HTTPRequestException):
            self.opener.open(request(url))

    def test_server_hanging_up_during_the_handshake(self):
        with RawServer(lambda sock: sock.recv(4096)) as server:
            url = f"https://{LOCALHOST}:{server.port}/"
            with self.assertRaises(HTTPRequestException):
                self.opener.open(request(url))

    def test_invalid_proxy(self):
        self.assertRaises(BaseFrameworkException, HTTPSHandler, "no-port")


class TestHTTPSProxy(OpenerTestCase):
    def setUp(self):
        self.proxy = ConnectProxy(refuse={"127.0.0.1:1"}).start()
        self.addCleanup(self.proxy.stop)
        self.use_handler(HTTPSHandler(f"{LOCALHOST}:{self.proxy.port}", cf))

    def test_https_through_connect_proxy(self):
        server = self.serve(
            {"/": Response(body="tunneled")}, tls_context=server_tls_context()
        )

        response = self.opener.open(request(server.url()))

        self.assertEqual(response.read(), b"tunneled")
        self.assertEqual(self.proxy.targets, [server.netloc])

    def test_requests_can_skip_the_proxy(self):
        server = self.serve(
            {"/": Response(body="direct")}, tls_context=server_tls_context()
        )

        response = self.opener.open(request(server.url(), use_proxy=False))

        self.assertEqual(response.read(), b"direct")
        self.assertEqual(self.proxy.targets, [])

    def test_proxy_refusing_the_tunnel(self):
        with self.assertRaisesRegex(OSError, "Proxy connection failed: 407"):
            self.opener.open(request("https://127.0.0.1:1/"))

    def test_tunnel_to_a_server_without_tls(self):
        server = self.serve({"/": Response(body="plain")})

        with self.assertRaises(HTTPRequestException):
            self.opener.open(request(f"https://{server.netloc}/"))


class TestProxySetup(unittest.TestCase):
    def setUp(self):
        self.conn = ProxyHTTPConnection(LOCALHOST, 3128)

    def test_default_ports(self):
        self.conn.proxy_setup("http://w3af.org/")
        self.assertEqual((self.conn._real_host, self.conn._real_port), ("w3af.org", 80))

        self.conn.proxy_setup("https://w3af.org/")
        self.assertEqual(self.conn._real_port, 443)

    def test_explicit_port(self):
        self.conn.proxy_setup("https://w3af.org:8443/")
        self.assertEqual(self.conn._real_port, 8443)

    def test_invalid_urls(self):
        self.assertRaises(ValueError, self.conn.proxy_setup, "w3af.org")
        self.assertRaises(ValueError, self.conn.proxy_setup, "ftp://w3af.org/")


class TestConnections(unittest.TestCase):
    def test_connection_representation(self):
        conn = HTTPConnection(LOCALHOST, 80)
        conn.inc_req_count()

        self.assertRegex(
            repr(conn), r"<KeepAliveHTTPConnection [0-9a-f]{16} - Request #1>"
        )
        self.assertIn("timeout:None", str(conn))
        self.assertIn("timeout:3", str(HTTPConnection(LOCALHOST, 80, timeout=3)))

    def test_create_connection_from_a_source_address(self):
        with RouteServer({"/": Response()}) as server:
            sock = create_connection(
                (LOCALHOST, server.port), timeout=5, source_address=(LOCALHOST, 0)
            )
            with sock:
                self.assertEqual(sock.getsockname()[0], LOCALHOST)

    def test_create_connection_failure(self):
        self.assertRaises(
            ConnectionRefusedError, create_connection, (LOCALHOST, closed_port())
        )


class TestHTTPResponse(unittest.TestCase):
    def get_response(self, raw_response, method="GET"):
        with RawServer(
            lambda sock: (read_http_head(sock), sock.sendall(raw_response))
        ) as server:
            conn = HTTPConnection(LOCALHOST, server.port, timeout=5)
            conn.request(method, "/")
            response = conn.getresponse()
            body = response.read()
        conn.close()
        return response, body

    def test_chunked_body(self):
        response, body = self.get_response(
            b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n"
            b"3\r\nabc\r\n0\r\n\r\n"
        )
        self.assertEqual(body, b"abc")
        self.assertFalse(response.will_close)

    def test_duplicated_content_length_uses_the_smallest(self):
        _, body = self.get_response(
            b"HTTP/1.1 200 OK\r\nContent-Length: 5, 3\r\n\r\nabcde"
        )
        self.assertEqual(body, b"abc")

    def test_invalid_and_negative_content_length(self):
        for length in (b"abc", b"-1"):
            response, body = self.get_response(
                b"HTTP/1.1 200 OK\r\nContent-Length: " + length + b"\r\n\r\nxyz"
            )
            self.assertEqual(body, b"xyz")
            self.assertTrue(response.will_close)

    def test_bodiless_status_codes(self):
        for status in (b"204 No Content", b"304 Not Modified"):
            response, body = self.get_response(b"HTTP/1.1 " + status + b"\r\n\r\n")
            self.assertEqual(body, b"")
            self.assertEqual(response.length, 0)

    def test_keep_alive_negotiation(self):
        cases = [
            (b"HTTP/1.1 200 OK\r\nKeep-Alive: timeout=5, max=1\r\n", True),
            (b"HTTP/1.0 200 OK\r\nConnection: Keep-Alive\r\n", False),
            (b"HTTP/1.1 200 OK\r\nConnection: close\r\n", True),
            (b"HTTP/1.1 200 OK\r\n", False),
            (b"HTTP/1.0 200 OK\r\nProxy-Connection: keep-alive\r\n", False),
            (b"HTTP/1.0 200 OK\r\n", True),
        ]
        for head, will_close in cases:
            response, _ = self.get_response(head + b"Content-Length: 0\r\n\r\n")
            self.assertEqual(bool(response.will_close), will_close, head)

    def test_closed_response_reads_empty_and_begin_is_idempotent(self):
        with RawServer(
            lambda sock: (
                read_http_head(sock),
                sock.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok"),
            )
        ) as server:
            conn = HTTPConnection(LOCALHOST, server.port, timeout=5)
            conn.request("GET", "/")
            response = conn.getresponse()
            response.begin()
            response.close()
            self.assertEqual(response.read(), b"")
            conn.close()

        self.assertIsInstance(response, HTTPResponse)


class TestUtils(unittest.TestCase):
    def test_to_utf8_raw(self):
        self.assertEqual(utils.to_utf8_raw("á"), "á".encode())
        self.assertEqual(utils.to_utf8_raw(b"raw"), b"raw")

    def test_request_body_bytes(self):
        self.assertEqual(utils.request_body_bytes(b"a=1"), b"a=1")
        self.assertEqual(utils.request_body_bytes("á"), "á".encode())
        self.assertEqual(utils.request_body_bytes(123), b"123")

    def test_debug_and_error_logging(self):
        with self.assertLogs(utils.LOGGER, "DEBUG") as logs:
            utils.debug("debug message")
            utils.error("error message")

        self.assertEqual(
            logs.output,
            [
                f"DEBUG:{utils.LOGGER.name}:[keepalive] debug message",
                f"ERROR:{utils.LOGGER.name}:[keepalive] error message",
            ],
        )


class TestConnectionManager(unittest.TestCase):
    URL = "http://127.0.0.1:8080/"

    def setUp(self):
        self.cm = ConnectionManager()
        self.cm.GET_AVAILABLE_CONNECTION_RETRY_SECS = 0.01
        self.cm.GET_AVAILABLE_CONNECTION_RETRY_MAX_TIME = 0.05
        self.request = request(self.URL)

    @staticmethod
    def factory(req):
        return HTTPConnection(req.host)

    def get(self, req=None):
        return self.cm.get_available_connection(req or self.request, self.factory)

    def test_free_connections_are_reused(self):
        self.cm.MAX_CONNECTIONS = 1

        conn = self.get()
        self.assertEqual(self.cm.get_all(), {conn})
        self.cm.free_connection(conn)
        self.assertIsNone(conn.current_request_start)

        self.assertIs(self.get(), conn)
        self.assertEqual(self.cm.get_connections_total("127.0.0.1:8080"), 1)
        self.assertEqual(self.cm.get_all("w3af.org:80"), set())

    def test_new_connection_closes_an_unused_free_connection(self):
        self.cm.MAX_CONNECTIONS = 1
        conn = self.get()
        self.cm.free_connection(conn)

        fresh = self.get(request(self.URL, new_connection=True))

        self.assertIsNot(fresh, conn)
        self.assertEqual(self.cm.get_all(), {fresh})

    def test_new_connection_waits_for_room_in_the_pool(self):
        self.cm.MAX_CONNECTIONS = 1
        self.get()

        self.assertRaises(
            ConnectionPoolException, self.get, request(self.URL, new_connection=True)
        )

    def test_full_pool_without_free_connections(self):
        self.cm.MAX_CONNECTIONS = 1
        other_host = self.get(request("http://127.0.0.1:9090/"))
        self.cm.free_connection(other_host)
        self.get()

        self.assertRaises(ConnectionPoolException, self.get)

    def test_waiting_for_a_connection_is_logged(self):
        self.cm.MAX_CONNECTIONS = 1
        self.cm.GET_AVAILABLE_CONNECTION_RETRY_MAX_TIME = 10
        conn = self.get()
        threading.Timer(0.1, self.cm.free_connection, [conn]).start()

        with self.assertLogs(connection_manager.LOGGER, "DEBUG") as logs:
            self.assertIs(self.get(), conn)

        self.assertTrue(any("Waited" in line for line in logs.output))

    def test_replace_connection(self):
        bad = self.get()
        new = self.cm.replace_connection(bad, self.request, self.factory)

        self.assertIsNot(new, bad)
        self.assertEqual(self.cm.get_all(), {new})

    def test_remove_connection_ignores_errors_while_closing(self):
        sock, peer = socket.socketpair()
        self.addCleanup(peer.close)
        context = OpenSSL.SSL.Context(OpenSSL.SSL.TLS_METHOD)
        tls = OpenSSL.SSL.Connection(context, sock)
        tls.set_connect_state()
        conn = self.get()
        conn.sock = SSLSocket(tls, sock)

        self.cm.remove_connection(conn, reason="unittest")

        self.assertEqual(self.cm.get_connections_total(), 0)
        sock.close()

    def test_free_unknown_connection(self):
        conn = HTTPConnection(LOCALHOST)
        self.cm.free_connection(conn)
        self.assertEqual(self.cm.get_connections_total(), 0)

    def test_stats_are_logged_periodically(self):
        self.cm.LOG_STATS_EVERY = 1
        host_port = "127.0.0.1:8080"

        with self.assertLogs(connection_manager.LOGGER, "DEBUG") as logs:
            self.cm.log_stats(host_port)
        self.assertIn("There are no connections marked as in use", logs.output[-1])

        started = self.get()
        waiting = self.get()
        waiting.current_request_start = None
        self.cm.free_connection(self.get())
        with self.assertLogs(connection_manager.LOGGER, "DEBUG") as logs:
            self.cm.log_stats(host_port)
        self.assertIn(f"({started.id}, ", logs.output[-1])
        self.assertNotIn(waiting.id, logs.output[-1])

        started.current_request_start = None
        with self.assertLogs(connection_manager.LOGGER, "DEBUG") as logs:
            self.cm.log_stats(host_port)
        self.assertIn("have started to send the first byte", logs.output[-1])

    def test_stats_are_not_logged_every_request(self):
        self.cm.LOG_STATS_EVERY = 2
        with self.assertNoLogs(connection_manager.LOGGER, "DEBUG"):
            self.cm.log_stats("127.0.0.1:8080")

    def test_cleanup_broken_connections(self):
        stuck = self.get()
        idle_start = self.get()
        busy = self.get()
        stuck.current_request_start = time.time() - 1000
        idle_start.current_request_start = None

        stale = self.get()
        self.cm.free_connection(stale)
        stale.connection_manager_move_ts = time.time() - 1000
        unmoved = self.get()
        self.cm.free_connection(unmoved)
        unmoved.connection_manager_move_ts = None
        recent = self.get()
        self.cm.free_connection(recent)

        self.cm.cleanup_broken_connections()

        self.assertEqual(self.cm.get_all(), {idle_start, busy, unmoved, recent})


cf = Config()
