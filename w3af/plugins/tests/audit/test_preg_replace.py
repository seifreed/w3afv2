"""
test_preg_replace.py

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

from w3af.plugins.tests.audit.vulnerable_responses import html_page, request_params
from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest

PREG_URL = "http://mock/audit/preg_replace/"

INDEX_BODY = """
<a href="preg_all_regex.php?regex=/a/&amp;text=abc">Whole regex</a>
<a href="preg_section_regex.php?search=a&amp;text=abc">Regex section</a>
<a href="preg_quoted.php?search=a&amp;text=abc">Quoted regex</a>
<a href="preg_broken.php?search=a">Broken regex</a>
"""

PREG_WARNING = (
    "<b>Warning</b>:  preg_replace() [<a href='function.preg-replace'>"
    "function.preg-replace</a>]: Compilation failed: unmatched parentheses"
    " at offset 1"
)


def preg_replace(pattern, text):
    """Emulate PHP's preg_replace compiling a user controlled pattern."""
    try:
        compiled = re.compile(pattern.strip("/"))
    except re.error:
        return PREG_WARNING
    return compiled.sub("x", text)


def preg_site(mock_response, request, uri, response_headers):
    page = request.uri.removeprefix(PREG_URL).split("?")[0]
    params = request_params(request)
    text = params.get("text", "")

    if page == "preg_all_regex.php":
        result = preg_replace(params.get("regex", ""), text)
    elif page == "preg_section_regex.php":
        result = preg_replace(f"/{params.get('search', '')}/", text)
    elif page == "preg_quoted.php":
        result = preg_replace(f"/{re.escape(params.get('search', ''))}/", text)
    elif page == "preg_broken.php":
        result = preg_replace("/(/", params.get("search", ""))
    else:
        return html_page(response_headers, "Not found", status=404)

    return html_page(response_headers, result)


class TestPreg(PluginTest):

    target_url = PREG_URL

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(PREG_URL, INDEX_BODY),
        MockResponse(re.compile(f"{PREG_URL}.+"), preg_site),
    ]

    _run_configs: ClassVar[dict] = {
        "cfg": {
            "target": target_url,
            "plugins": {
                "audit": (PluginConfig("preg_replace"),),
                "crawl": (
                    PluginConfig(
                        "web_spider", ("only_forward", True, PluginConfig.BOOL)
                    ),
                ),
            },
        }
    }

    def test_found_preg(self):
        cfg = self._run_configs["cfg"]
        self._scan(cfg["target"], cfg["plugins"])

        vulns = self.kb.get("preg_replace", "preg_replace")
        expected_results = (
            ("preg_all_regex.php", "regex"),
            ("preg_section_regex.php", "search"),
        )

        self.assertAllVulnNamesEqual("Unsafe preg_replace usage", vulns)
        self.assertExpectedVulnsFound(expected_results, vulns)
