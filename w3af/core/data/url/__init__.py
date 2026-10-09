import ssl
from typing import Any


# The stdlib http clients verify certificates by default (PEP 476), the scanner
# must be able to talk to any target so we disable it globally
# https://github.com/andresriancho/w3af/issues/8115
def _create_default_https_context(*args: Any, **kwargs: Any) -> ssl.SSLContext:
    return ssl._create_unverified_context(*args, **kwargs)


ssl._create_default_https_context = _create_default_https_context
