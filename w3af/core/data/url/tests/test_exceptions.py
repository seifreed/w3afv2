import unittest
from urllib.request import Request

from w3af.core.data.url.exceptions import (
    ConnectionPoolException,
    HTTPRequestException,
)


class TestHTTPRequestException(unittest.TestCase):

    def test_stores_message_and_request_url(self):
        request = Request("https://example.test/path")
        exception = HTTPRequestException("request failed", request)

        self.assertEqual(str(exception), "request failed")
        self.assertEqual(exception.get_url(), "https://example.test/path")

    def test_url_is_none_without_request(self):
        exception = HTTPRequestException("request failed")

        self.assertIsNone(exception.get_url())

    def test_connection_pool_exception_is_http_request_exception(self):
        exception = ConnectionPoolException("pool unavailable")

        self.assertIsInstance(exception, HTTPRequestException)
        self.assertEqual(str(exception), "pool unavailable")
