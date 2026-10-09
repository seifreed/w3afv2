import http.client
import queue
import threading
import unittest
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.response import addinfourl

from w3af.core.controllers.output_manager.log_sink import LogSink
from w3af.core.data.dc.headers import Headers
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.url.extended_urllib import ExtendedUrllib
from w3af.core.data.url.handlers.http_log import HTTPLogHandler
from w3af.core.data.url.http_request import HTTPRequest
from w3af.core.data.url.http_response import HTTPResponse
from w3af.core.data.url.opener_settings import OpenerSettings


class TestHTTPLogHandler(unittest.TestCase):
    def test_opener_sends_http_messages_to_the_injected_sink(self):
        messages = queue.Queue()
        uri_opener = ExtendedUrllib(LogSink(messages).log_http)
        settings = uri_opener.settings
        settings.build_openers()
        handlers = [
            handler
            for handler in settings.get_custom_opener().handlers
            if isinstance(handler, HTTPLogHandler)
        ]
        request_url = URL("http://example.test/")
        request = HTTPRequest(request_url)
        response = HTTPResponse(200, "body", Headers(), request_url, request_url)

        self.assertEqual(len(handlers), 1)
        self.assertIs(handlers[0].http_response(request, response), response)
        self.assertEqual(messages.get(timeout=1), (("log_http", request, response), {}))

    def test_converts_standard_http_responses_and_preserves_the_id(self):
        class ResponseHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"body")

        server = HTTPServer(("127.0.0.1", 0), ResponseHandler)
        server_thread = threading.Thread(target=server.serve_forever)
        server_thread.start()
        connection = http.client.HTTPConnection(*server.server_address)
        messages = queue.Queue()
        url = URL(f"http://127.0.0.1:{server.server_port}/")
        request = HTTPRequest(url)

        try:
            connection.request("GET", "/")
            raw_response = connection.getresponse()
            wrapped_response = addinfourl(
                raw_response, raw_response.headers, url.url_string
            )
            wrapped_response.code = raw_response.status
            wrapped_response.msg = raw_response.reason
            wrapped_response.id = 42

            handler = HTTPLogHandler(LogSink(messages).log_http)
            handler.http_response(request, wrapped_response)

            logged_message = messages.get(timeout=1)[0]
            self.assertEqual(logged_message[0], "log_http")
            self.assertIs(logged_message[1], request)
            self.assertEqual(logged_message[2].id, 42)
            self.assertEqual(logged_message[2].get_body(), b"body")
        finally:
            connection.close()
            server.shutdown()
            server.server_close()
            server_thread.join()

    def test_rejects_non_framework_requests(self):
        messages = queue.Queue()
        url = URL("http://example.test/")
        request = urllib.request.Request(url.url_string)
        response = HTTPResponse(200, "body", Headers(), url, url)
        handler = HTTPLogHandler(LogSink(messages).log_http)

        with self.assertRaises(TypeError):
            handler.http_response(request, response)

    def test_opener_without_sink_does_not_install_http_log_handler(self):
        settings = OpenerSettings()
        settings.build_openers()

        self.assertFalse(
            any(
                isinstance(handler, HTTPLogHandler)
                for handler in settings.get_custom_opener().handlers
            )
        )
