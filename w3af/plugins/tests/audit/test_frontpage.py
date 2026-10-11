"""
test_frontpage.py

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
from typing import ClassVar

from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest

DOCUMENT_NAME_RE = re.compile(r"document_name=([^;]+);")


class UploadedDocuments:
    """
    The documents stored by the author.dll handler of the canned server.
    """

    def __init__(self):
        self.contents = {}


class AuthorDllResponse(MockResponse):
    """
    Stores the document uploaded with the FrontPage "put document" method,
    like an insecurely configured author.dll does.
    """

    def __init__(self, url, documents):
        super().__init__(url, body="", method="POST", status=200)
        self.documents = documents

    def get_response(self, http_request, uri, response_headers):
        header, _, content = http_request.body.decode("utf-8").partition("\n")
        document_match = DOCUMENT_NAME_RE.search(header)
        if document_match is None:
            raise ValueError("FrontPage upload has no document name")
        document_name = document_match.group(1)
        self.documents.contents["/" + document_name.lstrip("/")] = content
        return super().get_response(http_request, uri, response_headers)


class UploadedDocumentResponse(MockResponse):
    """
    Serves the documents uploaded through author.dll
    """

    def __init__(self, url, documents):
        super().__init__(url, body="", method="GET", status=200)
        self.documents = documents

    def get_response(self, http_request, uri, response_headers):
        content = self.documents.contents.get(http_request.path)
        if content is None:
            return MockResponse.get_404(http_request, uri, response_headers)

        response_headers.update(self.headers)
        return self.status, response_headers, content


class TestFrontpage(PluginTest):

    target_url = "http://httpretty"

    FRONTPAGE_BODY = (
        'FPVersion="1.2.3"\n'
        'FPAdminScriptUrl="/admin"\n'
        'FPAuthorScriptUrl="/author"\n'
    )

    UPLOADED_DOCUMENTS = UploadedDocuments()

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(
            "http://httpretty/_vti_inf.html",
            body=FRONTPAGE_BODY,
            method="GET",
            status=200,
        ),
        AuthorDllResponse("http://httpretty/author", UPLOADED_DOCUMENTS),
        UploadedDocumentResponse(
            re.compile(r"http://httpretty/[a-zA-Z]{6}\.html$"), UPLOADED_DOCUMENTS
        ),
    ]

    _run_configs: ClassVar[dict] = {
        "cfg": {
            "target": target_url,
            "plugins": {
                "infrastructure": (PluginConfig("frontpage_version"),),
                "audit": (PluginConfig("frontpage"),),
            },
        }
    }

    def setUp(self):
        super().setUp()
        self.UPLOADED_DOCUMENTS.contents.clear()

    def test_upload(self):
        cfg = self._run_configs["cfg"]
        self._scan(cfg["target"], cfg["plugins"])

        vulns = self.kb.get("frontpage", "frontpage")

        self.assertEqual(len(vulns), 1, vulns)

        vuln = vulns[0]

        uploaded_paths = list(self.UPLOADED_DOCUMENTS.contents)
        self.assertEqual(len(uploaded_paths), 1, uploaded_paths)
        self.assertEqual(vuln.get_url().get_path(), uploaded_paths[0])
        self.assertEqual(vuln.get_name(), "Insecure Frontpage extensions configuration")
