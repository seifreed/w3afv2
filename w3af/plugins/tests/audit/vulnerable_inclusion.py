"""
vulnerable_inclusion.py

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

import http.client
import re
import urllib.parse

from w3af.plugins.tests.audit.vulnerable_responses import html_page, request_param

REMOTE_URL = re.compile(r"^https?://", re.IGNORECASE)
PHP_BLOCK = re.compile(r"<\?(?:php)?(.*?)\?>", re.DOTALL)
PHP_ECHO = re.compile(r'echo\s+"([^"]*)"\s*;')
FETCH_TIMEOUT = 10

MISSING_FILE_WARNING = (
    "<b>Warning</b>: include(%s): failed to open stream: No such file or directory"
)
NETWORK_WARNING = "<b>Warning</b>: include(): php_network_getaddresses: getaddrinfo"


def execute_php(source):
    """
    Run the <?php echo "text"; ?> and <? echo "text"; ?> blocks of the source,
    leaving the rest of the text as it is.
    """

    def run_block(block):
        return "".join(PHP_ECHO.findall(block.group(1)))

    return PHP_BLOCK.sub(run_block, source)


class RemoteFetcher:
    """
    Downloads the files that the vulnerable application includes: the sites
    in proxied_hosts are reached through a proxy, the rest directly.
    """

    def __init__(self, proxied_hosts=()):
        self.proxied_hosts = tuple(proxied_hosts)
        self.proxy_address = None

    def use_proxy(self, host, port):
        self.proxy_address = (host, port)

    def fetch(self, url):
        parts = urllib.parse.urlsplit(url)

        if parts.hostname in self.proxied_hosts and self.proxy_address:
            proxy_host, proxy_port = self.proxy_address
            connection = http.client.HTTPConnection(
                proxy_host, proxy_port, timeout=FETCH_TIMEOUT
            )
            request_target = url
        else:
            connection = http.client.HTTPConnection(
                parts.hostname, parts.port or 80, timeout=FETCH_TIMEOUT
            )
            request_target = parts.path or "/"

        try:
            connection.request("GET", request_target)
            return connection.getresponse().read().decode("utf-8", errors="replace")
        finally:
            connection.close()


class IncludePage:
    """
    A page which includes the file named by the "file" parameter, such as the
    PHP application include($_GET['file']) with allow_url_include enabled.

    :param fetcher: Downloads the included remote files
    :param execute: Run the PHP code of the included file, or just show it
    :param network_error: Report a failed download, as PHP does when the
                          included host can not be resolved
    """

    def __init__(self, fetcher, execute=True, network_error=False):
        self.fetcher = fetcher
        self.execute = execute
        self.network_error = network_error

    def __call__(self, mock_response, request, uri, response_headers):
        included = request_param(request, "file")

        if not REMOTE_URL.match(included):
            return html_page(response_headers, MISSING_FILE_WARNING % included)

        if self.network_error:
            return html_page(response_headers, NETWORK_WARNING)

        content = self.fetcher.fetch(included)
        body = execute_php(content) if self.execute else content
        return html_page(response_headers, body)
