"""
test_lfi.py

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

from w3af.core.controllers.ci.wavsep import get_wavsep_http
from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest

CONFIG = {
    "audit": (PluginConfig("lfi"),),
    "crawl": (PluginConfig("web_spider", ("only_forward", True, PluginConfig.BOOL)),),
}


LFI_URL = "http://mock/audit/local_file_read/"

ETC_USERS_FILE = (
    "root:x:0:0:root:/root:/bin/bash\n"
    "daemon:x:1:1:daemon:/usr/sbin:/bin/sh\n"
    "www-data:x:33:33:www-data:/var/www:/bin/sh\n"
)

LFI_INDEX = """
<a href="local_file_read.py?file=section.txt">Read</a>
<a href="local_file_read_full_path.py?file=/var/www/section.txt">Read full path</a>
<a href="safe_file_read.py?file=section.txt">Safe read</a>
"""


def read_file(value):
    """Emulate opening `value` and returning its content, without sanitising."""
    normalized = value.split("\x00")[0]
    if normalized.endswith("etc/passwd"):
        return ETC_USERS_FILE
    return "This is the content of the section.txt file"


def lfi_page(mock_response, request, uri, response_headers):
    value = urllib.parse.parse_qs(urllib.parse.urlsplit(request.uri).query).get(
        "file", [""]
    )[0]
    response_headers["Content-Type"] = "text/html"
    return 200, response_headers, read_file(value)


def safe_file_read(mock_response, request, uri, response_headers):
    """Only serves files from a fixed directory, path traversal is stripped."""
    response_headers["Content-Type"] = "text/html"
    return 200, response_headers, "This is the content of the section.txt file"


LFI_PAGES = {
    "local_file_read.py": lfi_page,
    "local_file_read_full_path.py": lfi_page,
    "safe_file_read.py": safe_file_read,
}


def lfi_site(mock_response, request, uri, response_headers):
    page = urllib.parse.urlsplit(request.uri).path.rsplit("/", 1)[-1]
    responder = LFI_PAGES.get(page)
    if responder is None:
        response_headers["Content-Type"] = "text/html"
        return 200, response_headers, LFI_INDEX
    return responder(mock_response, request, uri, response_headers)


class TestLFI(PluginTest):

    target_url = LFI_URL

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(re.compile(f"{re.escape(LFI_URL)}.*"), lfi_site)
    ]

    def test_found_lfi(self):
        self._scan(self.target_url, CONFIG)

        vulns = self.kb.get("lfi", "lfi")

        expected = [
            ("local_file_read.py", "file"),
            ("local_file_read_full_path.py", "file"),
        ]

        self.assertAllVulnNamesEqual("Local file inclusion vulnerability", vulns)
        self.assertExpectedVulnsFound(expected, vulns)


class TestWAVSEP500Error(PluginTest):

    base_path = "/wavsep/active/LFI/LFI-Detection-Evaluation-GET-500Error/"

    target_url = get_wavsep_http(base_path)

    def test_find_lfi_wavsep_error(self):
        expected_path_param = {
            (
                "Case01-LFI-FileClass-FilenameContext-Unrestricted-OSPath-DefaultFullInput-AnyPathReq-Read.jsp",
                "target",
            ),
            (
                "Case02-LFI-FileClass-FilenameContext-Unrestricted-FileDirective-DefaultFullInput-AnyPathReq-Read.jsp",
                "target",
            ),
            (
                "Case03-LFI-FileClass-FilenameContext-Unrestricted-OSPath-DefaultRelativeInput-AnyPathReq-Read.jsp",
                "target",
            ),
            (
                "Case04-LFI-FileClass-FilenameContext-Unrestricted-FileDirective-DefaultRelativeInput-AnyPathReq-Read.jsp",
                "target",
            ),
            (
                "Case05-LFI-FileClass-FilenameContext-Unrestricted-OSPath-DefaultInvalidInput-AnyPathReq-Read.jsp",
                "target",
            ),
            (
                "Case06-LFI-FileClass-FilenameContext-Unrestricted-FileDirective-DefaultInvalidInput-AnyPathReq-Read.jsp",
                "target",
            ),
            (
                "Case07-LFI-FileClass-FilenameContext-Unrestricted-OSPath-DefaultEmptyInput-AnyPathReq-Read.jsp",
                "target",
            ),
            (
                "Case08-LFI-FileClass-FilenameContext-Unrestricted-FileDirective-DefaultEmptyInput-AnyPathReq-Read.jsp",
                "target",
            ),
            (
                "Case09-LFI-FileClass-FilenameContext-Unrestricted-OSPath-DefaultFullInput-NoPathReq-Read.jsp",
                "target",
            ),
            (
                "Case11-LFI-FileClass-FilenameContext-Unrestricted-OSPath-DefaultInvalidInput-NoPathReq-Read.jsp",
                "target",
            ),
            (
                "Case13-LFI-FileClass-FilenameContext-Unrestricted-OSPath-DefaultEmptyInput-NoPathReq-Read.jsp",
                "target",
            ),
            (
                "Case15-LFI-FileClass-FilenameContext-Unrestricted-OSPath-DefaultFullInput-SlashPathReq-Read.jsp",
                "target",
            ),
            (
                "Case17-LFI-FileClass-FilenameContext-Unrestricted-OSPath-DefaultInvalidInput-SlashPathReq-Read.jsp",
                "target",
            ),
            (
                "Case19-LFI-FileClass-FilenameContext-Unrestricted-OSPath-DefaultEmptyInput-SlashPathReq-Read.jsp",
                "target",
            ),
            (
                "Case21-LFI-FileClass-FilenameContext-Unrestricted-OSPath-DefaultFullInput-BackslashPathReq-Read.jsp",
                "target",
            ),
            (
                "Case22-LFI-FileClass-FilenameContext-Unrestricted-OSPath-DefaultInvalidInput-BackslashPathReq-Read.jsp",
                "target",
            ),
            (
                "Case23-LFI-FileClass-FilenameContext-Unrestricted-OSPath-DefaultEmptyInput-BackslashPathReq-Read.jsp",
                "target",
            ),
            (
                "Case28-LFI-ContextStream-FilenameContext-Unrestricted-OSPath-DefaultFullInput-NoPathReq-Read.jsp",
                "target",
            ),
            (
                "Case29-LFI-ContextStream-FilenameContext-Unrestricted-OSPath-DefaultInvalidInput-NoPathReq-Read.jsp",
                "target",
            ),
            (
                "Case30-LFI-ContextStream-FilenameContext-Unrestricted-OSPath-DefaultEmptyInput-NoPathReq-Read.jsp",
                "target",
            ),
            (
                "Case31-LFI-ContextStream-FilenameContext-Unrestricted-OSPath-DefaultFullInput-SlashPathReq-Read.jsp",
                "target",
            ),
            (
                "Case32-LFI-ContextStream-FilenameContext-Unrestricted-OSPath-DefaultInvalidInput-SlashPathReq-Read.jsp",
                "target",
            ),
            (
                "Case33-LFI-ContextStream-FilenameContext-Unrestricted-OSPath-DefaultEmptyInput-SlashPathReq-Read.jsp",
                "target",
            ),
            (
                "Case34-LFI-ContextStream-FilenameContext-Unrestricted-OSPath-DefaultFullInput-BackslashPathReq-Read.jsp",
                "target",
            ),
            (
                "Case35-LFI-ContextStream-FilenameContext-Unrestricted-OSPath-DefaultInvalidInput-BackslashPathReq-Read.jsp",
                "target",
            ),
            (
                "Case36-LFI-ContextStream-FilenameContext-Unrestricted-OSPath-DefaultEmptyInput-BackslashPathReq-Read.jsp",
                "target",
            ),
            (
                "Case38-LFI-FileClass-FilenameContext-BackslashTraversalValidation-OSPath-DefaultFullInput-AnyPathReq-Read.jsp",
                "target",
            ),
            (
                "Case39-LFI-FileClass-FilenameContext-UnixTraversalValidation-OSPath-DefaultFullInput-NoPathReq-Read.jsp",
                "target",
            ),
            (
                "Case40-LFI-FileClass-FilenameContext-WindowsTraversalValidation-OSPath-DefaultFullInput-NoPathReq-Read.jsp",
                "target",
            ),
            (
                "Case41-LFI-FileClass-FilenameContext-UnixTraversalValidation-OSPath-DefaultFullInput-SlashPathReq-Read.jsp",
                "target",
            ),
            (
                "Case42-LFI-FileClass-FilenameContext-WindowsTraversalValidation-OSPath-DefaultFullInput-SlashPathReq-Read.jsp",
                "target",
            ),
            (
                "Case43-LFI-FileClass-FilenameContext-UnixTraversalValidation-OSPath-DefaultFullInput-BackslashPathReq-Read.jsp",
                "target",
            ),
            (
                "Case44-LFI-FileClass-FilenameContext-WindowsTraversalValidation-OSPath-DefaultFullInput-BackslashPathReq-Read.jsp",
                "target",
            ),
            (
                "Case47-LFI-ContextStream-FilenameContext-UnixTraversalValidation-OSPath-DefaultFullInput-NoPathReq-Read.jsp",
                "target",
            ),
            (
                "Case48-LFI-ContextStream-FilenameContext-WindowsTraversalValidation-OSPath-DefaultFullInput-NoPathReq-Read.jsp",
                "target",
            ),
            (
                "Case49-LFI-ContextStream-FilenameContext-UnixTraversalValidation-OSPath-DefaultFullInput-SlashPathReq-Read.jsp",
                "target",
            ),
            (
                "Case50-LFI-ContextStream-FilenameContext-WindowsTraversalValidation-OSPath-DefaultFullInput-SlashPathReq-Read.jsp",
                "target",
            ),
            (
                "Case51-LFI-ContextStream-FilenameContext-UnixTraversalValidation-OSPath-DefaultFullInput-BackslashPathReq-Read.jsp",
                "target",
            ),
            (
                "Case52-LFI-ContextStream-FilenameContext-WindowsTraversalValidation-OSPath-DefaultFullInput-BackslashPathReq-Read.jsp",
                "target",
            ),
            (
                "Case54-LFI-FileClass-FilenameContext-BackslashTraversalRemoval-OSPath-DefaultFullInput-AnyPathReq-Read.jsp",
                "target",
            ),
            (
                "Case55-LFI-FileClass-FilenameContext-UnixTraversalRemoval-OSPath-DefaultFullInput-NoPathReq-Read.jsp",
                "target",
            ),
            (
                "Case56-LFI-FileClass-FilenameContext-WindowsTraversalRemoval-OSPath-DefaultFullInput-NoPathReq-Read.jsp",
                "target",
            ),
            (
                "Case57-LFI-FileClass-FilenameContext-UnixTraversalRemoval-OSPath-DefaultFullInput-SlashPathReq-Read.jsp",
                "target",
            ),
            (
                "Case58-LFI-FileClass-FilenameContext-WindowsTraversalRemoval-OSPath-DefaultFullInput-SlashPathReq-Read.jsp",
                "target",
            ),
            (
                "Case59-LFI-FileClass-FilenameContext-UnixTraversalRemoval-OSPath-DefaultFullInput-BackslashPathReq-Read.jsp",
                "target",
            ),
            (
                "Case60-LFI-FileClass-FilenameContext-WindowsTraversalRemoval-OSPath-DefaultFullInput-BackslashPathReq-Read.jsp",
                "target",
            ),
            (
                "Case63-LFI-ContextStream-FilenameContext-UnixTraversalRemoval-OSPath-DefaultFullInput-NoPathReq-Read.jsp",
                "target",
            ),
            (
                "Case64-LFI-ContextStream-FilenameContext-WindowsTraversalRemoval-OSPath-DefaultFullInput-NoPathReq-Read.jsp",
                "target",
            ),
            (
                "Case65-LFI-ContextStream-FilenameContext-UnixTraversalRemoval-OSPath-DefaultFullInput-SlashPathReq-Read.jsp",
                "target",
            ),
            (
                "Case66-LFI-ContextStream-FilenameContext-WindowsTraversalRemoval-OSPath-DefaultFullInput-SlashPathReq-Read.jsp",
                "target",
            ),
            (
                "Case67-LFI-ContextStream-FilenameContext-UnixTraversalRemoval-OSPath-DefaultFullInput-BackslashPathReq-Read.jsp",
                "target",
            ),
            (
                "Case68-LFI-ContextStream-FilenameContext-WindowsTraversalRemoval-OSPath-DefaultFullInput-BackslashPathReq-Read.jsp",
                "target",
            ),
        }

        # None is OK to miss -> 100% coverage, that's our goal!
        ok_to_miss = {
            "Case10-LFI-FileClass-FilenameContext-Unrestricted-FileDirective-DefaultFullInput-NoPathReq-Read.jsp",
            "Case12-LFI-FileClass-FilenameContext-Unrestricted-FileDirective-DefaultInvalidInput-NoPathReq-Read.jsp",
            "Case14-LFI-FileClass-FilenameContext-Unrestricted-FileDirective-DefaultEmptyInput-NoPathReq-Read.jsp",
            "Case16-LFI-FileClass-FilenameContext-Unrestricted-FileDirective-DefaultFullInput-SlashPathReq-Read.jsp",
            "Case18-LFI-FileClass-FilenameContext-Unrestricted-FileDirective-DefaultInvalidInput-SlashPathReq-Read.jsp",
            "Case20-LFI-FileClass-FilenameContext-Unrestricted-FileDirective-DefaultEmptyInput-SlashPathReq-Read.jsp",
            "Case24-LFI-FileClass-FilenameContext-Unrestricted-FileDirective-DefaultFullInput-BackslashPathReq-Read.jsp",
            "Case25-LFI-ContextStream-FilenameContext-Unrestricted-OSPath-DefaultFullInput-AnyPathReq-Read.jsp",
            "Case26-LFI-ContextStream-FilenameContext-Unrestricted-OSPath-DefaultInvalidInput-AnyPathReq-Read.jsp",
            "Case27-LFI-ContextStream-FilenameContext-Unrestricted-OSPath-DefaultEmptyInput-AnyPathReq-Read.jsp",
            "Case45-LFI-ContextStream-FilenameContext-SlashTraversalValidation-OSPath-DefaultFullInput-AnyPathReq-Read.jsp",
            "Case46-LFI-ContextStream-FilenameContext-BackslashTraversalValidation-OSPath-DefaultFullInput-AnyPathReq-Read.jsp",
            "Case53-LFI-FileClass-FilenameContext-SlashTraversalRemoval-OSPath-DefaultFullInput-AnyPathReq-Read.jsp",
            "Case61-LFI-ContextStream-FilenameContext-SlashTraversalRemoval-OSPath-DefaultFullInput-AnyPathReq-Read.jsp",
            "Case62-LFI-ContextStream-FilenameContext-BackslashTraversalRemoval-OSPath-DefaultFullInput-AnyPathReq-Read.jsp",
            #
            # These are confirmed not to work when WAVSEP is running in Linux,
            # so there is nothing w3af can improve to detect them:
            #
            # https://code.google.com/p/wavsep/issues/detail?id=10
            # https://github.com/sectooladdict/wavsep/issues/5
            #
            "Case37-LFI-FileClass-FilenameContext-SlashTraversalValidation-OSPath-DefaultFullInput-AnyPathReq-Read.jsp",
        }
        skip_startwith = {"index.jsp"}
        kb_addresses = {("lfi", "lfi")}

        self._scan_assert(
            CONFIG, expected_path_param, ok_to_miss, kb_addresses, skip_startwith
        )
