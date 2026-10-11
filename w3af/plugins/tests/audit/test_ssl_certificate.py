"""
test_ssl_certificate.py

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

import socket
import tempfile
import threading
import unittest

from w3af.core.data.kb.knowledge_base import DBKnowledgeBase
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.request.fuzzable_request import FuzzableRequest
from w3af.plugins.audit.ssl_certificate import (
    CertificateError,
    _dnsname_to_pat,
    match_hostname,
    ssl_certificate,
)
from w3af.plugins.tests.audit.local_pki import (
    Identity,
    create_certificate_authority,
    issue_certificate,
)
from w3af.plugins.tests.audit.local_tls_server import LocalTlsServer
from w3af.plugins.tests.helper import PluginConfig, PluginTest

LOCAL_HOST = "localhost"
EXPECTED_STRINGS = ("localhost", "commonName", "TLS_AES")


class LocalTlsServers:
    """
    Starts TLS servers whose certificates are issued by a throw-away CA.
    """

    def __init__(self, test_case):
        directory = tempfile.TemporaryDirectory()
        test_case.addCleanup(directory.cleanup)
        self.test_case = test_case
        self.directory = directory.name
        self.authority = create_certificate_authority()
        self.ca_file = self.authority.write_certificate(self.directory, "ca.pem")

    def serve(self, dns_names=(LOCAL_HOST,), days_valid=365, signed_by_ca=True):
        """
        :return: The port of a started TLS server
        """
        authority = self.authority if signed_by_ca else None
        issued = issue_certificate(
            Identity(LOCAL_HOST), dns_names, days_valid, authority
        )
        bundle = issued.write_server_bundle(self.directory, f"server-{id(issued)}.pem")

        server = LocalTlsServer(bundle)
        server.start()
        self.test_case.addCleanup(server.stop)
        return server.port


def free_closed_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class TestSSLCertificate(PluginTest):

    def setUp(self):
        super().setUp()
        self.servers = LocalTlsServers(self)

    def scan_https(self, port, trust_local_ca=True, min_expire_days=30):
        options = [("min_expire_days", min_expire_days, PluginConfig.INT)]
        if trust_local_ca:
            options.append(("ca_file_name", self.servers.ca_file, PluginConfig.STR))

        plugins = {"audit": (PluginConfig("ssl_certificate", *options),)}
        self._scan(f"https://{LOCAL_HOST}:{port}/", plugins, verify_targets=False)

    def kb_items(self, name):
        return self.kb.get("ssl_certificate", name)

    def test_self_signed_certificate_is_reported(self):
        port = self.servers.serve(signed_by_ca=False)

        self.scan_https(port, trust_local_ca=False)

        vulns = self.kb_items("invalid_ssl_cert")
        self.assertEqual(1, len(vulns))

        vuln = vulns[0]
        self.assertEqual("Invalid SSL certificate", vuln.get_name())
        self.assertEqual(f"https://{LOCAL_HOST}:{port}/", str(vuln.get_url()))
        self.assertEqual(1, len(self.kb_items("certificate")))

    def test_trusted_certificate_has_no_vulnerabilities(self):
        port = self.servers.serve()

        self.scan_https(port)

        self.assertEqual([], self.kb_items("invalid_ssl_cert"))
        self.assertEqual([], self.kb_items("invalid_ssl_connect"))
        self.assertEqual([], self.kb_items("ssl_soon_expire"))

        info = self.kb_items("certificate")
        self.assertEqual(1, len(info))

        # Now some tests around specific details of the found info
        info = info[0]
        self.assertEqual("SSL Certificate dump", info.get_name())
        self.assertEqual(f"https://{LOCAL_HOST}:{port}/", str(info.get_url()))

        for expected_string in EXPECTED_STRINGS:
            self.assertIn(expected_string, info.get_desc())

    def test_certificate_close_to_expiration_is_reported(self):
        port = self.servers.serve(days_valid=5)

        self.scan_https(port)

        infos = self.kb_items("ssl_soon_expire")
        self.assertEqual(1, len(infos))
        self.assertEqual("Soon to expire SSL certificate", infos[0].get_name())
        self.assertEqual([], self.kb_items("invalid_ssl_cert"))

    def test_expiration_threshold_is_configurable(self):
        port = self.servers.serve(days_valid=60)

        self.scan_https(port, min_expire_days=90)

        self.assertEqual(1, len(self.kb_items("ssl_soon_expire")))

    def test_certificate_issued_for_another_host_is_reported(self):
        port = self.servers.serve(dns_names=("other.example",))

        self.scan_https(port)

        vulns = self.kb_items("invalid_ssl_cert")
        self.assertEqual(1, len(vulns))
        self.assertIn("other.example", vulns[0].get_desc())

    def test_http_targets_are_not_analyzed(self):
        plugin = ssl_certificate()
        request = FuzzableRequest(URL(f"http://{LOCAL_HOST}/"))

        plugin.audit(request, None, "http-target")

        self.assertEqual([], self.kb_items("certificate"))


class SslCertificatePluginTest(unittest.TestCase):

    def setUp(self):
        kb.cleanup()
        self.addCleanup(kb.cleanup)
        self.plugin = ssl_certificate()

    def audit(self, url):
        self.plugin.audit(FuzzableRequest(URL(url)), None, "plugin-test")

    def kb_items(self, name):
        return kb.get("ssl_certificate", name)

    def test_unreachable_server_is_ignored(self):
        self.audit(f"https://127.0.0.1:{free_closed_port()}/")

        self.assertEqual([], self.kb_items("certificate"))
        self.assertEqual([], self.kb_items("invalid_ssl_cert"))

    def test_server_that_does_not_speak_tls_is_ignored(self):
        with socket.socket() as plain_server:
            plain_server.bind(("127.0.0.1", 0))
            plain_server.listen(10)
            acceptor = threading.Thread(
                target=self.close_connections, args=(plain_server,)
            )
            acceptor.daemon = True
            acceptor.start()

            self.audit(f"https://127.0.0.1:{plain_server.getsockname()[1]}/")

        self.assertEqual([], self.kb_items("certificate"))

    @staticmethod
    def close_connections(server_socket):
        while True:
            try:
                connection, _ = server_socket.accept()
            except OSError:
                return
            connection.close()

    def test_a_domain_is_only_analyzed_once(self):
        servers = LocalTlsServers(self)
        port = servers.serve()

        self.plugin.set_options(self.options(servers.ca_file))
        self.audit(f"https://{LOCAL_HOST}:{port}/first")
        self.audit(f"https://{LOCAL_HOST}:{port}/second")

        self.assertEqual(1, len(self.kb_items("certificate")))

    def options(self, ca_file):
        options = self.plugin.get_options()
        options["ca_file_name"].set_value(ca_file)
        return options

    def test_unsupported_protocol_is_ignored(self):
        servers = LocalTlsServers(self)
        port = servers.serve()
        invalid_protocol = -1

        result = self.plugin._ssl_connect_specific_protocol(
            LOCAL_HOST, port, ssl_version=invalid_protocol
        )

        self.assertIsNone(result)

    def test_options_are_read_back(self):
        servers = LocalTlsServers(self)
        options = self.plugin.get_options()
        options["min_expire_days"].set_value(45)
        options["ca_file_name"].set_value(servers.ca_file)

        self.plugin.set_options(options)

        new_options = self.plugin.get_options()
        self.assertEqual(45, new_options["min_expire_days"].get_value())
        self.assertEqual(servers.ca_file, new_options["ca_file_name"].get_value())

    def test_long_description_names_the_options(self):
        description = self.plugin.get_long_desc()

        self.assertIn("min_expire_days", description)
        self.assertIn("ca_file_name", description)


class TestMatchHostname(unittest.TestCase):

    def test_empty_certificate_is_rejected(self):
        with self.assertRaises(ValueError):
            match_hostname({}, "example.com")

    def test_subject_alt_name_is_matched(self):
        cert = {"subjectAltName": (("DNS", "example.com"),)}

        self.assertIsNone(match_hostname(cert, "example.com"))

    def test_wildcard_matches_a_single_label(self):
        cert = {"subjectAltName": (("DNS", "*.example.com"),)}

        self.assertIsNone(match_hostname(cert, "www.example.com"))
        with self.assertRaises(CertificateError):
            match_hostname(cert, "a.b.example.com")

    def test_common_name_is_used_without_subject_alt_name(self):
        cert = {"subject": ((("commonName", "example.com"),),)}

        self.assertIsNone(match_hostname(cert, "example.com"))

    def test_common_name_mismatch_names_the_certificate_host(self):
        cert = {"subject": ((("commonName", "example.com"),),)}

        with self.assertRaisesRegex(CertificateError, "doesn't match example.com"):
            match_hostname(cert, "other.com")

    def test_mismatch_with_many_names_lists_all_of_them(self):
        cert = {"subjectAltName": (("DNS", "a.com"), ("DNS", "b.com"))}

        with self.assertRaisesRegex(CertificateError, "either of a.com, b.com"):
            match_hostname(cert, "other.com")

    def test_certificate_without_names_is_rejected(self):
        cert = {"subject": ((("organizationName", "w3af"),),)}

        with self.assertRaisesRegex(CertificateError, "no appropriate"):
            match_hostname(cert, "example.com")

    def test_too_many_wildcards_are_rejected(self):
        with self.assertRaises(CertificateError):
            _dnsname_to_pat("***.example.com")

    def test_wildcard_inside_a_label_is_a_pattern(self):
        pattern = _dnsname_to_pat("w*.example.com")

        self.assertIsNotNone(pattern.match("www.example.com"))
        self.assertIsNone(pattern.match("a.example.com"))


kb = DBKnowledgeBase()
