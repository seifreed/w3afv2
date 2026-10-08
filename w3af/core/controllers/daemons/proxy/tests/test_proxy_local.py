import threading
import unittest
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from w3af.core.controllers.daemons.proxy import Proxy, ProxyHandler
from w3af.core.data.url.extended_urllib import ExtendedUrllib


class LocalOriginHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b"proxy-integration-ok"
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass


class TestProxyLocal(unittest.TestCase):
    def setUp(self):
        self.origin = ThreadingHTTPServer(("127.0.0.1", 0), LocalOriginHandler)
        self.origin_thread = threading.Thread(
            target=self.origin.serve_forever, daemon=True
        )
        self.origin_thread.start()
        self.proxy = Proxy("127.0.0.1", 0, ExtendedUrllib(), ProxyHandler)
        self.proxy.start()
        self.proxy.wait_for_start()

    def tearDown(self):
        self.proxy.stop()
        self.proxy.join(timeout=5)
        self.origin.shutdown()
        self.origin.server_close()
        self.origin_thread.join(timeout=5)

    def test_forwards_request_and_response(self):
        proxy_url = f"http://127.0.0.1:{self.proxy.get_port()}"
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({"http": proxy_url})
        )

        response = opener.open(f"http://127.0.0.1:{self.origin.server_port}/")

        self.assertEqual(response.read(), b"proxy-integration-ok")
        self.assertEqual(self.proxy.total_handled_requests, 1)
