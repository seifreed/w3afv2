"""
test_ssl_wrapper.py

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

import http.client
import socket
import ssl
import threading
import time
import unittest
from datetime import UTC, datetime

import OpenSSL
from cryptography.hazmat.primitives.serialization import Encoding

from w3af.core.data.url.handlers.tests.local_server import (
    LOCALHOST,
    LocalServer,
    RawServer,
    Reply,
    certificate,
    server_tls_context,
)
from w3af.core.data.url.openssl_wrapper.ssl_wrapper import (
    CERT_REQUIRED,
    NOT_AFTER_FORMAT,
    OpenSSLReformattedError,
    SSLSocket,
    wrap_socket,
)

TLS = OpenSSL.SSL.TLS_METHOD


class TestOpenSSLReformattedError(unittest.TestCase):
    def test_str_of_a_generic_exception(self):
        """
        :see: https://github.com/andresriancho/w3af/issues/8663
        """
        e = Exception("Message")
        self.assertEqual(str(OpenSSLReformattedError(e)), "Message")

    def test_str_of_an_openssl_error_stack(self):
        e = OpenSSL.SSL.Error(
            [("SSL routines", "ssl3_get_record", "decryption failed or bad record mac")]
        )
        self.assertEqual(
            str(OpenSSLReformattedError(e)),
            "*:ssl3_get_record:decryption failed or bad record mac (glob)",
        )

    def test_str_inside_ssl_error(self):
        e = OpenSSL.SSL.Error("OpenSSL.SSL.Error Message")
        se = ssl.SSLError("ssl.SSLError Message", OpenSSLReformattedError(e))

        self.assertIn("ssl.SSLError Message", str(se))
        self.assertIn("OpenSSL.SSL.Error Message", str(se.args[1]))


def tls_socket_pair(timeout=5, server_cert=None):
    """
    :return: (client SSLSocket created by wrap_socket, server ssl.SSLSocket)
             connected through a socketpair.
    """
    client_sock, server_sock = socket.socketpair()
    context = server_tls_context(server_cert)
    server = {}

    def accept():
        server_sock.settimeout(timeout)
        server["sock"] = context.wrap_socket(server_sock, server_side=True)

    thread = threading.Thread(target=accept)
    thread.start()
    client = wrap_socket(client_sock, ssl_version=TLS, timeout=timeout)
    thread.join(timeout)
    return client, server["sock"]


def read_https(server, cert_reqs=ssl.CERT_NONE, ca_certs=None, **kwargs):
    sock = socket.create_connection((LOCALHOST, server.port), 5)
    ssl_sock = wrap_socket(
        sock,
        cert_reqs=cert_reqs,
        ca_certs=ca_certs,
        ssl_version=TLS,
        server_hostname="localhost",
        **kwargs,
    )
    ssl_sock.sendall(b"GET / HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n")
    response = http.client.HTTPResponse(ssl_sock)
    response.begin()
    body = response.read()
    return ssl_sock, response, body


class TestWrapSocket(unittest.TestCase):
    def test_https_request_and_peer_certificate(self):
        cert = certificate()
        with LocalServer({"/": Reply(body="secure")}, tls=True) as server:
            ssl_sock, response, body = read_https(server, timeout=5)

        self.assertEqual(response.status, 200)
        self.assertEqual(body, b"secure")

        peer_cert = ssl_sock.getpeercert()
        self.assertEqual(peer_cert["subject"], ((("commonName", "localhost"),),))
        self.assertEqual(peer_cert["subjectAltName"], [("DNS", "localhost")])
        self.assertEqual(
            datetime.strptime(peer_cert["notAfter"], NOT_AFTER_FORMAT)
            .replace(tzinfo=UTC)
            .date(),
            cert.certificate.not_valid_after_utc.date(),
        )
        self.assertEqual(
            ssl_sock.getpeercert(binary_form=True),
            cert.certificate.public_bytes(Encoding.DER),
        )
        ssl_sock.close()

    def test_verified_handshake_with_trusted_ca(self):
        cert = certificate()
        with LocalServer({"/": Reply(body="trusted")}, tls=True) as server:
            ssl_sock, _, body = read_https(
                server,
                cert_reqs=CERT_REQUIRED,
                ca_certs=str(cert.cert_file),
                timeout=socket._GLOBAL_DEFAULT_TIMEOUT,
            )
        ssl_sock.close()
        self.assertEqual(body, b"trusted")

    def test_bad_ca_certs(self):
        with socket.socket() as sock, self.assertRaisesRegex(
            ssl.SSLError, "Bad ca_certs"
        ):
            wrap_socket(sock, ca_certs=__file__)

    def test_certificate_without_san_and_common_name(self):
        cert = certificate(common_name=None, with_san=False)
        context = server_tls_context(cert)
        with LocalServer({"/": Reply()}, tls_context=context) as server:
            ssl_sock, _, _ = read_https(server)
        peer_cert = ssl_sock.getpeercert()
        ssl_sock.close()

        self.assertEqual(peer_cert["subject"], ((("commonName", None),),))
        self.assertEqual(peer_cert["subjectAltName"], [])

    def test_handshake_times_out_when_the_server_is_silent(self):
        with RawServer(lambda sock: sock.recv(4096) and time.sleep(2)) as server:
            sock = socket.create_connection((LOCALHOST, server.port), 5)
            with sock, self.assertRaisesRegex(ssl.SSLError, "timed out"):
                wrap_socket(sock, ssl_version=TLS, timeout=0.3)

    def test_handshake_times_out_when_the_server_dribbles(self):
        def dribble(sock):
            sock.recv(4096)
            for byte in b"\x16\x03\x03\x40\x00":
                sock.send(bytes([byte]))
                time.sleep(0.15)

        with RawServer(dribble) as server:
            sock = socket.create_connection((LOCALHOST, server.port), 5)
            with sock, self.assertRaisesRegex(ssl.SSLError, "timed out"):
                wrap_socket(sock, ssl_version=TLS, timeout=0.4)

    def test_handshake_with_a_server_that_hangs_up(self):
        with RawServer(lambda sock: sock.recv(4096)) as server:
            sock = socket.create_connection((LOCALHOST, server.port), 5)
            with sock, self.assertRaises(ssl.SSLError):
                wrap_socket(sock, ssl_version=TLS, timeout=5)


class TestSSLSocket(unittest.TestCase):
    def setUp(self):
        self.client, self.server = tls_socket_pair()
        self.addCleanup(self.server.close)

    def test_attributes_come_from_the_connection_or_the_socket(self):
        self.assertIsNotNone(self.client.get_cipher_name())
        self.assertEqual(self.client.gettimeout(), 5)
        self.client.close()

    def test_makefile_only_supports_binary_reads(self):
        self.assertRaises(ValueError, self.client.makefile, "r")
        self.client.close()

    def test_close_waits_for_files_and_tolerates_a_closed_peer(self):
        response_file = self.client.makefile()
        self.server.sendall(b"data")

        self.client.close()
        self.assertFalse(self.client.closed)
        self.assertEqual(response_file.read(4), b"data")

        self.server.close()
        response_file.close()
        self.assertTrue(self.client.closed)

        self.client.close()
        self.assertTrue(self.client.closed)

    def test_close_reports_unexpected_tls_errors(self):
        sock, _peer = socket.socketpair()
        self.addCleanup(sock.close)
        self.addCleanup(_peer.close)
        connection = OpenSSL.SSL.Connection(OpenSSL.SSL.Context(TLS), sock)
        connection.set_connect_state()
        ssl_sock = SSLSocket(connection, sock)

        self.assertRaises(OpenSSL.SSL.Error, ssl_sock.close)
        self.assertRaises(ssl.SSLError, ssl_sock.getpeercert)
        self.client.close()

    def test_recv_returns_data_once_it_arrives(self):
        def send_later():
            time.sleep(0.2)
            self.server.sendall(b"late")

        thread = threading.Thread(target=send_later)
        thread.start()
        self.assertEqual(self.client.recv(4), b"late")
        thread.join()
        self.client.close()

    def test_recv_timeout_reads_as_closed(self):
        self.client.settimeout(0.2)
        self.assertEqual(self.client.recv(4), b"")
        self.client.close()

    def test_recv_after_peer_close(self):
        self.server.close()
        self.assertEqual(self.client.recv(4), b"")
        self.client.close()

    def test_sendall_waits_for_the_peer_to_read(self):
        payload = b"x" * (4 * 1024 * 1024)
        received = []

        def read_later():
            time.sleep(0.2)
            total = 0
            while total < len(payload):
                chunk = self.server.recv(65536)
                total += len(chunk)
            received.append(total)

        thread = threading.Thread(target=read_later)
        thread.start()
        self.client.sendall(payload)
        thread.join(10)
        self.assertEqual(received, [len(payload)])
        self.client.close()

    def test_sendall_times_out_when_the_peer_never_reads(self):
        self.client.settimeout(0.2)
        self.assertRaises(TimeoutError, self.client.sendall, b"x" * (4 * 1024 * 1024))
