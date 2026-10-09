"""
digital_certificate.py

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

import datetime
import ipaddress
import os
import socket

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from w3af.core.paths import get_home_dir

KEY_SIZE = 2048
PUBLIC_EXPONENT = 65537
VALIDITY = datetime.timedelta(days=10 * 365)
ORGANIZATION = "w3af.org"
PRIVATE_FILE_FLAGS = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
PRIVATE_FILE_MODE = 0o600


def subject_alternative_name(host: str) -> x509.GeneralName:
    """
    :return: An IP address SAN when the host is an IP, a DNS name otherwise
    """
    try:
        return x509.IPAddress(ipaddress.ip_address(host))
    except ValueError:
        return x509.DNSName(host)


def build_self_signed_certificate(
    host: str, key: rsa.RSAPrivateKey
) -> x509.Certificate:
    name = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "CA"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, ORGANIZATION),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, ORGANIZATION),
            x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, ORGANIZATION),
            x509.NameAttribute(NameOID.COMMON_NAME, host),
        ]
    )
    public_key = key.public_key()
    not_before = datetime.datetime.now(datetime.UTC)

    return (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(public_key)
        .serial_number(x509.random_serial_number())
        .not_valid_before(not_before)
        .not_valid_after(not_before + VALIDITY)
        .add_extension(
            x509.SubjectAlternativeName([subject_alternative_name(host)]),
            critical=False,
        )
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(
            x509.SubjectKeyIdentifier.from_public_key(public_key), critical=False
        )
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(public_key),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )


class SSLCertificate:
    def __init__(self) -> None:
        ssl_dir = os.path.join(get_home_dir(), "ssl")
        self.key_path = os.path.join(ssl_dir, "w3af.key")
        self.cert_path = os.path.join(ssl_dir, "w3af.crt")
        os.makedirs(ssl_dir, exist_ok=True)

    def generate(self, host: str | None = None) -> None:
        """
        :param host: The hostname used to generate the certificate
        :return: None, we write the cert and key to files
        """
        host = host or socket.gethostname()
        key = rsa.generate_private_key(
            public_exponent=PUBLIC_EXPONENT, key_size=KEY_SIZE
        )
        certificate = build_self_signed_certificate(host, key)

        with open(self.cert_path, "wb") as cert_file:
            cert_file.write(certificate.public_bytes(serialization.Encoding.PEM))

        key_descriptor = os.open(self.key_path, PRIVATE_FILE_FLAGS, PRIVATE_FILE_MODE)
        with os.fdopen(key_descriptor, "wb") as key_file:
            key_file.write(
                key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.TraditionalOpenSSL,
                    encryption_algorithm=serialization.NoEncryption(),
                )
            )

    def get_cert_key(self, host: str | None = None) -> tuple[str, str]:
        """
        :param host: The hostname used to generate the certificate
        :return: A tuple containing the certificate path and the key path, the
                 format accepted by werkzeug as ssl_context
        """
        if not os.path.exists(self.cert_path) or not os.path.exists(self.key_path):
            self.generate(host=host)

        return self.cert_path, self.key_path
