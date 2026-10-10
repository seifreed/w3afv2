"""
local_pki.py

Copyright 2026 w3af contributors

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
import os
from dataclasses import dataclass

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

PEM = serialization.Encoding.PEM
NO_ENCRYPTION = serialization.NoEncryption()
PRIVATE_FORMAT = serialization.PrivateFormat.PKCS8


@dataclass(frozen=True)
class Identity:
    """
    The subject of a certificate.
    """

    common_name: str
    organization: str = "w3af tests"
    locality: str = "Moscow"
    country: str = "RU"

    def to_name(self):
        return x509.Name(
            [
                x509.NameAttribute(NameOID.COMMON_NAME, self.common_name),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, self.organization),
                x509.NameAttribute(NameOID.LOCALITY_NAME, self.locality),
                x509.NameAttribute(NameOID.COUNTRY_NAME, self.country),
            ]
        )


@dataclass(frozen=True)
class KeyAndCertificate:
    key: ec.EllipticCurvePrivateKey
    certificate: x509.Certificate

    @property
    def certificate_pem(self):
        return self.certificate.public_bytes(PEM)

    @property
    def key_pem(self):
        return self.key.private_bytes(PEM, PRIVATE_FORMAT, NO_ENCRYPTION)

    def write_certificate(self, directory, file_name):
        return write_file(directory, file_name, self.certificate_pem)

    def write_server_bundle(self, directory, file_name):
        """
        :return: The path of a PEM file with the certificate and its key
        """
        return write_file(directory, file_name, self.certificate_pem + self.key_pem)


def write_file(directory, file_name, content):
    path = os.path.join(directory, file_name)
    with open(path, "wb") as output:
        output.write(content)
    return path


def build_certificate(
    identity, issuer, issuer_key, public_key, days_valid, dns_names, is_ca
):
    now = datetime.datetime.now(datetime.timezone.utc)
    builder = (
        x509.CertificateBuilder()
        .subject_name(identity.to_name())
        .issuer_name(issuer)
        .public_key(public_key)
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=days_valid))
        .add_extension(x509.BasicConstraints(ca=is_ca, path_length=None), True)
    )

    if dns_names:
        names = [x509.DNSName(name) for name in dns_names]
        builder = builder.add_extension(x509.SubjectAlternativeName(names), False)

    return builder.sign(issuer_key, hashes.SHA256())


def create_certificate_authority(common_name="w3af test CA"):
    identity = Identity(common_name)
    key = ec.generate_private_key(ec.SECP256R1())
    certificate = build_certificate(
        identity, identity.to_name(), key, key.public_key(), 365, (), True
    )
    return KeyAndCertificate(key, certificate)


def issue_certificate(identity, dns_names, days_valid=365, authority=None):
    """
    :param authority: Sign the certificate with this CA, or self sign it
    """
    key = ec.generate_private_key(ec.SECP256R1())
    signer = authority.key if authority else key
    issuer = authority.certificate.subject if authority else identity.to_name()

    certificate = build_certificate(
        identity, issuer, signer, key.public_key(), days_valid, dns_names, False
    )
    return KeyAndCertificate(key, certificate)
