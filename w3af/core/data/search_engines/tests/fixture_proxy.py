"""
fixture_proxy.py

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

import http.server
import threading
import urllib.parse

import w3af.core.data.kb.config as cf
from w3af.core.data.url.extended_urllib import ExtendedUrllib
from w3af.core.data.url.opener_settings import OpenerSettings
from w3af.core.filesystem import create_temp_dir

DROP_CONNECTION = object()


class FixtureProxy:
    """
    An in-process HTTP proxy that answers every request with a fixture.

    Search engines build absolute URLs for well known hosts; routing a real
    ExtendedUrllib through this proxy lets the tests exercise the complete
    HTTP stack without reaching the network.

    :param responder: Callable receiving the requested URL (a ParseResult)
                      and returning the body to send (str), or DROP_CONNECTION
                      to close the socket without answering.
    """

    def __init__(self, responder):
        self.requests = []
        self._previous_proxy = ()
        proxy = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                url = urllib.parse.urlparse(self.path)
                proxy.requests.append(url)
                body = responder(url)

                if body is DROP_CONNECTION:
                    self.close_connection = True
                    return

                payload = body.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *args):
                return None

        self._server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *exc_info):
        self._server.shutdown()
        self._server.server_close()
        # The proxy settings live in the global configuration: restore them so
        # later openers do not keep sending requests to this stopped proxy
        for name, value in self._previous_proxy:
            cf.cf.save(name, value)

    def query(self, index=-1):
        return dict(urllib.parse.parse_qsl(self.requests[index].query))

    def opener(self):
        """
        :return: An ExtendedUrllib which sends all its requests to this proxy
        """
        create_temp_dir()

        settings = OpenerSettings()
        self._previous_proxy = [
            (name, cf.cf.get(name)) for name in ("proxy_address", "proxy_port")
        ]
        options = settings.get_options()
        options["proxy_address"].set_value("127.0.0.1")
        options["proxy_port"].set_value(self._server.server_address[1])
        settings.set_options(options)

        uri_opener = ExtendedUrllib()
        uri_opener.settings = settings
        return uri_opener
