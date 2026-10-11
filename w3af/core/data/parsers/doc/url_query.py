"""Query-string parsing independent from the URL value object."""

import urllib.parse
from collections import OrderedDict

from w3af.core.data.constants.encodings import DEFAULT_ENCODING
from w3af.core.data.dc.query_string import QueryString

__all__ = ["parse_qs", "parse_qsl"]


def parse_qsl(qs, encoding=DEFAULT_ENCODING):
    """Parse a query string into ordered ``(name, value)`` pairs."""
    result = []
    for ampersand_pair in qs.split("&"):
        for name_value in ampersand_pair.split(";"):
            if not name_value:
                continue

            name, separator, value = name_value.partition("=")
            if not separator:
                value = ""

            decoded_name = urllib.parse.unquote(
                name.replace("+", " "), encoding=encoding, errors="ignore"
            )
            decoded_value = urllib.parse.unquote(
                value.replace("+", " "), encoding=encoding, errors="ignore"
            )
            result.append((decoded_name, decoded_value))

    return result


def parse_qs(qstr, encoding=DEFAULT_ENCODING):
    """Parse a URL-encoded string into a :class:`QueryString`."""
    if not isinstance(qstr, str):
        raise TypeError("parse_qs requires a basestring as input.")

    query_string = QueryString(encoding=encoding)
    values_by_name = OrderedDict()
    for name, value in parse_qsl(qstr, encoding=encoding):
        values_by_name.setdefault(name, []).append(value)

    query_string.update(values_by_name.items())
    return query_string
