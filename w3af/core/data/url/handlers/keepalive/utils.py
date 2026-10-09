import logging
import os

KA_DEBUG = os.environ.get("KA_DEBUG", "0") == "1"
LOGGER = logging.getLogger(__name__)


def to_utf8_raw(unicode_or_str):
    if isinstance(unicode_or_str, str):
        # TODO: Is 'ignore' the best option here?
        return unicode_or_str.encode("utf-8", "ignore")
    return unicode_or_str


def debug(msg):
    if KA_DEBUG:
        LOGGER.debug("[keepalive] %s", msg)


def error(msg):
    if KA_DEBUG:
        LOGGER.error("[keepalive] %s", msg)
