"""
test_dav.py

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
import urllib.parse
from typing import ClassVar

from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest

PROPFIND_LISTING = (
    '<?xml version="1.0"?>'
    '<a:multistatus xmlns:a="DAV:"><a:response>'
    "<D:href>/index.html</D:href></a:response></a:multistatus>"
)

CONFIG = {"audit": (PluginConfig("dav"),)}


class DavStore:
    """Files uploaded through the HTTP PUT method."""

    def __init__(self):
        self.files = {}


def propfind_responder(mock_response, request, uri, response_headers):
    response_headers["Content-Type"] = "application/xml"
    return 207, response_headers, PROPFIND_LISTING


def put_forbidden(mock_response, request, uri, response_headers):
    response_headers["Content-Type"] = "text/html"
    return 403, response_headers, "<html>Forbidden</html>"


class WritableDirResponder(MockResponse):
    """A directory where PUT uploads a file that GET then serves."""

    def __init__(self, url, store):
        super().__init__(url, body="", method="PUT", status=201)
        self.store = store

    def get_response(self, http_request, uri, response_headers):
        path = urllib.parse.urlsplit(uri).path
        self.store.files[path] = http_request.body.decode("utf-8")
        response_headers.update(self.headers)
        return 201, response_headers, ""


class ServeUploadedResponder(MockResponse):
    """Serves the files uploaded to the writable directory."""

    def __init__(self, url, store):
        super().__init__(url, body="", method="GET", status=200)
        self.store = store

    def get_response(self, http_request, uri, response_headers):
        path = urllib.parse.urlsplit(uri).path
        content = self.store.files.get(path)
        response_headers.update(self.headers)
        if content is None:
            return MockResponse.get_404(http_request, uri, response_headers)
        return 200, response_headers, content


class TestDavWritable(PluginTest):

    target_url = "http://mock/webdav/writable/"
    store = DavStore()

    MOCK_RESPONSES: ClassVar[list] = [
        WritableDirResponder(re.compile(r"http://mock/webdav/writable/\w+$"), store),
        ServeUploadedResponder(re.compile(r"http://mock/webdav/writable/\w+$"), store),
        MockResponse(
            re.compile(r"http://mock/webdav/writable/$"),
            propfind_responder,
            method="PROPFIND",
        ),
    ]

    def setUp(self):
        super().setUp()
        self.store.files.clear()

    def test_found_writable_and_propfind(self):
        self._scan(self.target_url, CONFIG)

        vulns = self.kb.get("dav", "dav")

        self.assertEqual(
            {"Publicly writable directory", "Insecure DAV configuration"},
            {v.get_name() for v in vulns},
        )
        self.assertEqual({"PUT", "PROPFIND"}, {v.get_method() for v in vulns})
        self.assertEqual(1, len(self.store.files))


class TestDavNoPrivileges(PluginTest):
    """
    DAV is configured but the directory doesn't have the file-system
    permissions to allow the Apache process to write to it.
    """

    target_url = "http://mock/webdav/no-privileges/"

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(
            re.compile(r"http://mock/webdav/no-privileges/\w+$"),
            put_forbidden,
            method="PUT",
        ),
        MockResponse(
            re.compile(r"http://mock/webdav/no-privileges/$"),
            propfind_responder,
            method="PROPFIND",
        ),
    ]

    def test_no_privileges(self):
        self._scan(self.target_url, CONFIG)

        vulns = self.kb.get("dav", "dav")

        names = {v.get_name() for v in vulns}
        self.assertIn("DAV incorrect configuration", names)
        self.assertIn("Insecure DAV configuration", names)


class TestDavNotVulnerable(PluginTest):

    target_url = "http://mock/webdav/safe/"

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(
            re.compile(r"http://mock/webdav/safe/\w+$"),
            body="Method not supported",
            method="PUT",
            status=403,
        ),
    ]

    def test_not_found_dav(self):
        self._scan(self.target_url, CONFIG)

        self.assertEqual(0, len(self.kb.get("dav", "dav")))
