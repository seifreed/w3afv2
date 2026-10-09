import logging
import os

LOGGER = logging.getLogger(__name__)

# The keep-alive internals are very verbose, only log them on demand
LOGGER.setLevel(
    logging.DEBUG if os.environ.get("KA_DEBUG", "0") == "1" else logging.CRITICAL + 1
)


def to_utf8_raw(unicode_or_str):
    if isinstance(unicode_or_str, str):
        # TODO: Is 'ignore' the best option here?
        return unicode_or_str.encode("utf-8", "ignore")
    return unicode_or_str


def request_body_bytes(data):
    """
    :return: The bytes to send on the wire for a request body which might be
             bytes, a string or a data container (form, JSON, etc.)
    """
    if isinstance(data, bytes):
        return data
    return to_utf8_raw(str(data))


def debug(msg):
    LOGGER.debug("[keepalive] %s", msg)


def error(msg):
    LOGGER.error("[keepalive] %s", msg)
