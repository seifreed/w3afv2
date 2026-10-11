"""Decode HTTP response bodies according to headers and content type."""

import logging
import re

from w3af.core.data.constants.encodings import DEFAULT_ENCODING
from w3af.core.data.misc.encoding import ESCAPED_CHAR, smart_unicode

DEFAULT_CHARSET = DEFAULT_ENCODING
CHARSET_EXTRACT_RE = re.compile(r"charset=\s*?([\w-]+)", re.IGNORECASE)
CHARSET_META_RE = re.compile(
    r'<meta.*?content=".*?charset=\s*?([\w-]+)".*?>', re.IGNORECASE
)

LOGGER = logging.getLogger(__name__)


class ResponseBodyDecoder:
    """Apply the response charset policy without owning response state."""

    def __init__(
        self,
        raw_body,
        charset,
        headers,
        is_text_or_html,
        response_id,
        debug=None,
    ):
        self._raw_body = raw_body
        self._charset = charset
        self._headers = headers
        self._is_text_or_html = is_text_or_html
        self._response_id = response_id
        self._debug = debug or LOGGER.debug

    def decode(self):
        charset = self._charset
        raw_body = self._raw_body
        content_type, _ = self._headers.iget("content-type", None)

        if isinstance(raw_body, str):
            body = raw_body
            charset = charset or self.guess_charset(raw_body, self._headers)
        elif content_type is None:
            body_text = self._decode_for_detection(raw_body)
            if CHARSET_META_RE.search(body_text):
                charset = self.guess_charset(raw_body, self._headers)
                # Do not keep the detection copy while decoding the body.
                del body_text
                body = smart_unicode(
                    raw_body, charset, errors=ESCAPED_CHAR, on_error_guess=False
                )
            else:
                body = raw_body
                charset = charset or DEFAULT_CHARSET

            if body:
                msg = (
                    "The remote web server failed to send the CONTENT_TYPE"
                    " header in HTTP response with id %s"
                )
                self._debug(msg, self._response_id)
        elif not self._is_text_or_html:
            body = raw_body
            charset = charset or DEFAULT_CHARSET
        else:
            charset = charset or self.guess_charset(raw_body, self._headers)
            body = self._decode_with_fallback(raw_body, charset)
            if body is None:
                charset = DEFAULT_CHARSET
                body = smart_unicode(
                    raw_body, charset, errors=ESCAPED_CHAR, on_error_guess=False
                )

        return body, charset

    @staticmethod
    def guess_charset(raw_body, headers):
        content_type, _ = headers.iget("content-type", None)
        charset_match = CHARSET_EXTRACT_RE.search(content_type or "")
        if charset_match:
            return charset_match.groups()[0].lower().strip()

        body_text = ResponseBodyDecoder._decode_for_detection(raw_body)
        charset_match = CHARSET_META_RE.search(body_text)
        if charset_match:
            return charset_match.groups()[0].lower().strip()

        return DEFAULT_CHARSET

    @staticmethod
    def _decode_for_detection(raw_body):
        if isinstance(raw_body, bytes):
            return raw_body.decode(DEFAULT_CHARSET, "ignore")
        return raw_body

    @staticmethod
    def _decode_with_fallback(raw_body, charset):
        try:
            return smart_unicode(
                raw_body, charset, errors=ESCAPED_CHAR, on_error_guess=False
            )
        except LookupError:
            msg = (
                f"Charset LookupError: unknown charset: {charset}; "
                f"ignored and set to default: {DEFAULT_CHARSET}"
            )
            LOGGER.debug(msg)
            return None
