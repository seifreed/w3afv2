"""
test_ssi.py

Copyright 2012 Andres Riancho

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

import re
import urllib.error
import urllib.parse
import urllib.request
from typing import ClassVar

from jinja2 import Template

from w3af.core.data.parsers.doc.url import URL
from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest

test_config = {
    "audit": (PluginConfig("ssi"),),
    "crawl": (PluginConfig("web_spider", ("only_forward", True, PluginConfig.BOOL)),),
}


class TestSSI(PluginTest):

    target_url = "http://mock/ssi.simple?message="

    class SSIMockResponse(MockResponse):
        def get_response(self, http_request, uri, response_headers):
            response_headers.update(self.headers)
            uri = urllib.parse.unquote(uri)
            seeds = re.findall("[1-9]{5}", uri)

            if len(seeds) == 2:
                body = "Contains evaluated user input {}{}".format(*tuple(seeds))
            else:
                body = "A regular body"

            return self.status, response_headers, body

    MOCK_RESPONSES: ClassVar[list] = [
        SSIMockResponse(re.compile(".*"), body=None, method="GET", status=200)
    ]

    def test_found_ssi(self):
        self._scan(self.target_url, test_config)
        vulns = self.kb.get("ssi", "ssi")

        self.assertEqual(1, len(vulns), vulns)

        # Now some tests around specific details of the found vuln
        vuln = vulns[0]

        self.assertEqual("message", vuln.get_token_name())
        self.assertEqual("Server side include vulnerability", vuln.get_name())
        self.assertEqual(
            URL(self.target_url).uri2url().url_string, vuln.get_url().url_string
        )


class TestJinja2SSI(PluginTest):

    target_url = "http://mock/ssi.simple?message="

    class SSIMockResponse(MockResponse):
        def get_response(self, http_request, uri, response_headers):
            response_headers.update(self.headers)
            uri = urllib.parse.unquote(uri)
            template = Template("Hello" + uri)
            body = template.render()
            return self.status, response_headers, body

    MOCK_RESPONSES: ClassVar[list] = [
        SSIMockResponse(re.compile(".*"), body=None, method="GET", status=200)
    ]

    def test_found_ssi(self):
        self._scan(self.target_url, test_config)
        vulns = self.kb.get("ssi", "ssi")

        self.assertEqual(1, len(vulns), vulns)

        # Now some tests around specific details of the found vuln
        vuln = vulns[0]

        self.assertEqual("message", vuln.get_token_name())
        self.assertEqual("Server side include vulnerability", vuln.get_name())
        self.assertEqual(
            URL(self.target_url).uri2url().url_string, vuln.get_url().url_string
        )


class GuestBook:
    """
    A guest book which stores the messages and renders them in another page,
    with the SSI exec directives evaluated by the web server.
    """

    EXEC_RE = re.compile(r'<!--#exec cmd="echo -n (\d+);echo -n (\d+)" -->')

    def __init__(self):
        self.messages = []

    def sign(self, mock_response, request, uri, response_headers):
        message = URL(uri).get_querystring().get("message", [""])[0]
        self.messages.append(self.EXEC_RE.sub(r"\1\2", message))
        response_headers["Content-Type"] = "text/html"
        return 200, response_headers, "<html>Thanks for signing!</html>"

    def view(self, mock_response, request, uri, response_headers):
        response_headers["Content-Type"] = "text/html"
        return 200, response_headers, f"<html>{'<br>'.join(self.messages)}</html>"


class TestPersistentSSI(PluginTest):

    target_url = "http://mock/guestbook/"
    guest_book = GuestBook()

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(
            target_url,
            '<a href="sign.shtml?message=hi">Sign</a><a href="view.shtml">View</a>',
        ),
        MockResponse(re.compile(r"http://mock/guestbook/sign.*"), guest_book.sign),
        MockResponse(re.compile(r"http://mock/guestbook/view.*"), guest_book.view),
    ]

    def test_found_persistent_ssi(self):
        self._scan(self.target_url, test_config)

        vulns = self.kb.get("ssi", "ssi")

        self.assertEqual(1, len(vulns), vulns)
        vuln = vulns[0]
        self.assertEqual("message", vuln.get_token_name())
        self.assertEqual(
            "Persistent server side include vulnerability", vuln.get_name()
        )
        self.assertEqual("http://mock/guestbook/sign.shtml", vuln.get_url().url_string)
