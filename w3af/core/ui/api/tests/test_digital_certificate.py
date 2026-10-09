"""
test_digital_certificate.py

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

import ipaddress
import os
import shutil
import ssl
import tempfile
import unittest

from cryptography import x509

from w3af.core.ui.api.utils.digital_certificate import SSLCertificate

HOME_DIR_VARIABLE = "W3AF_HOME_DIR"


class SSLCertificateTest(unittest.TestCase):
    def setUp(self):
        self.previous_home = os.environ.get(HOME_DIR_VARIABLE)
        self.home = tempfile.mkdtemp(prefix="w3af-home-")
        os.environ[HOME_DIR_VARIABLE] = self.home

    def tearDown(self):
        if self.previous_home is None:
            os.environ.pop(HOME_DIR_VARIABLE)
        else:
            os.environ[HOME_DIR_VARIABLE] = self.previous_home
        shutil.rmtree(self.home)

    def load_certificate(self, path):
        with open(path, "rb") as handle:
            return x509.load_pem_x509_certificate(handle.read())

    def alternative_names(self, certificate):
        extension = certificate.extensions.get_extension_for_class(
            x509.SubjectAlternativeName
        )
        return extension.value

    def test_generates_certificate_for_ip_address(self):
        cert_path, key_path = SSLCertificate().get_cert_key("127.0.0.1")

        certificate = self.load_certificate(cert_path)
        names = self.alternative_names(certificate)
        self.assertEqual(
            names.get_values_for_type(x509.IPAddress),
            [ipaddress.ip_address("127.0.0.1")],
        )

        context = ssl.create_default_context(cafile=cert_path)
        context.load_cert_chain(cert_path, key_path)

    def test_generates_certificate_for_host_name(self):
        cert_path, _ = SSLCertificate().get_cert_key("localhost")

        names = self.alternative_names(self.load_certificate(cert_path))
        self.assertEqual(names.get_values_for_type(x509.DNSName), ["localhost"])

    def test_reuses_existing_certificate(self):
        certificate = SSLCertificate()
        cert_path, _ = certificate.get_cert_key("localhost")
        first = self.load_certificate(cert_path)

        certificate.get_cert_key("127.0.0.1")

        self.assertEqual(self.load_certificate(cert_path), first)

    def test_defaults_to_the_machine_host_name(self):
        certificate = SSLCertificate()
        certificate.generate()

        names = self.alternative_names(self.load_certificate(certificate.cert_path))
        self.assertTrue(names.get_values_for_type(x509.DNSName))
