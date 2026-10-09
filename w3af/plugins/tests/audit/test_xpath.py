"""
test_xpath.py

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

from w3af.plugins.tests.audit.vulnerable_responses import html_page, request_param
from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest

XPATH_URL = "http://mock/audit/xpath/"
XPATH_ERROR = "XPathException: Invalid expression"

INDEX_BODY = """
<a href="xpath-attr-double.py?text=x">Double quoted attribute</a>
<a href="xpath-attr-single.py?text=x">Single quoted attribute</a>
<a href="xpath-attr-tag.py?text=x">Tag name</a>
<a href="xpath-attr-or.py?text=1">Numeric attribute</a>
<a href="xpath-safe.py?text=x">Escaped attribute</a>
<a href="xpath-error-page.py?text=x">Static error message</a>
"""

QUERIES = {
    "xpath-attr-double.py": '//user[@name="{}"]',
    "xpath-attr-single.py": "//user[@name='{}']",
    "xpath-attr-tag.py": "//{}/name",
    "xpath-attr-or.py": "//user[@id={} or @admin=1]",
}
SAFE_QUERY = QUERIES["xpath-attr-single.py"]


def is_valid_xpath(query):
    """A small XPath syntax check: balanced quotes, names and numbers."""
    without_strings = re.sub(r"\"[^\"]*\"|'[^']*'", "", query)
    return re.fullmatch(r"[\w/@\[\]= ]*", without_strings) is not None


def run_query(template, text):
    if is_valid_xpath(template.format(text)):
        return "No users found"
    return XPATH_ERROR


def xpath_site(mock_response, request, uri, response_headers):
    page = request.uri.removeprefix(XPATH_URL).split("?")[0]
    text = request_param(request, "text")

    if page in QUERIES:
        return html_page(response_headers, run_query(QUERIES[page], text))
    if page == "xpath-safe.py":
        escaped = text.replace("'", "").replace('"', "")
        return html_page(response_headers, run_query(SAFE_QUERY, escaped))
    if page == "xpath-error-page.py":
        return html_page(response_headers, f"Known issue: {XPATH_ERROR}")
    return html_page(response_headers, "Not found", status=404)


class TestXPATH(PluginTest):

    target_url = XPATH_URL

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(XPATH_URL, INDEX_BODY),
        MockResponse(re.compile(f"{XPATH_URL}.+"), xpath_site),
    ]

    _run_configs: ClassVar[dict] = {
        "cfg": {
            "target": target_url,
            "plugins": {
                "audit": (PluginConfig("xpath"),),
                "crawl": (
                    PluginConfig(
                        "web_spider", ("only_forward", True, PluginConfig.BOOL)
                    ),
                ),
            },
        }
    }

    def test_found_xpath(self):
        cfg = self._run_configs["cfg"]
        self._scan(cfg["target"], cfg["plugins"])

        vulns = self.kb.get("xpath", "xpath")
        self.assertEqual(4, len(vulns), vulns)

        vtitle = "XPATH injection vulnerability"
        all_titles = all(vtitle == vuln.get_name() for vuln in vulns)
        self.assertTrue(all_titles, vulns)

        expected = [
            ("xpath-attr-double.py", "text"),
            ("xpath-attr-tag.py", "text"),
            ("xpath-attr-or.py", "text"),
            ("xpath-attr-single.py", "text"),
        ]
        found = [
            (v.get_url().get_file_name(), v.get_mutant().get_token_name())
            for v in vulns
        ]
        self.assertEqual(set(expected), set(found))
