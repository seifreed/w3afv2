import ssl
from typing import Any


# The stdlib http clients verify certificates by default (PEP 476), the scanner
# must be able to talk to any target (expired, self-signed or otherwise broken
# certificates are exactly what it audits) so certificate verification is
# disabled globally and on purpose.
# https://github.com/andresriancho/w3af/issues/8115
def _create_default_https_context(*args: Any, **kwargs: Any) -> ssl.SSLContext:
    context = ssl.create_default_context(*args, **kwargs)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context


ssl._create_default_https_context = _create_default_https_context
