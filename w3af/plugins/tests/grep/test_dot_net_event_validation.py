"""
test_dot_net_event_validation.py

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

from typing import ClassVar

from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest

_VIEWSTATE = (
    '<input type="hidden" name="__VIEWSTATE" id="__VIEWSTATE" value="abc123" />'
)
_EVENTVALIDATION = (
    '<input type="hidden" name="__EVENTVALIDATION"'
    ' id="__EVENTVALIDATION" value="xyz789" />'
)
# Has VIEWSTATE and EVENTVALIDATION, but no VIEWSTATEENCRYPTED -> only the
# "ViewState encryption is disabled" finding.
_EVENT_VALIDATION_HTML = f"<html><body>{_VIEWSTATE}{_EVENTVALIDATION}</body></html>"
# Has VIEWSTATE, no EVENTVALIDATION, no VIEWSTATEENCRYPTED -> both findings.
_WITHOUT_EVENT_VALIDATION_HTML = f"<html><body>{_VIEWSTATE}</body></html>"

RUN_CONFIGS = {
    "cfg": {
        "target": None,
        "plugins": {
            "grep": (PluginConfig("dot_net_event_validation"),),
            "crawl": (
                PluginConfig("web_spider", ("only_forward", True, PluginConfig.BOOL)),
            ),
        },
    }
}


class TestEventValidation(PluginTest):

    target_url = "http://mock/grep/dot_net_event_validation/"

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(
            url=target_url,
            body=(
                '<a href="event_validation.html">1</a>'
                '<a href="without_event_validation.html">2</a>'
            ),
            method="GET",
            status=200,
        ),
        MockResponse(
            url=target_url + "event_validation.html",
            body=_EVENT_VALIDATION_HTML,
            method="GET",
            status=200,
        ),
        MockResponse(
            url=target_url + "without_event_validation.html",
            body=_WITHOUT_EVENT_VALIDATION_HTML,
            method="GET",
            status=200,
        ),
    ]

    def test_found_vuln(self):
        self._scan(self.target_url, RUN_CONFIGS["cfg"]["plugins"])

        vulns = self.kb.get("dot_net_event_validation", "dot_net_event_validation")

        expected_vulns = {
            (
                ("event_validation.html", "without_event_validation.html"),
                ".NET ViewState encryption is disabled",
            ),
            (("without_event_validation.html",), ".NET Event Validation is disabled"),
        }

        vulns_set = set()

        for vuln in vulns:
            name = vuln.get_name()

            filenames = []
            for url in vuln.get_urls():
                filenames.append(url.get_file_name())

            filenames.sort()
            vulns_set.add((tuple(filenames), name))

        self.assertEqual(expected_vulns, vulns_set)


class TestEventValidationGrouping(PluginTest):

    target_url = "http://mock/"

    html = (
        '<input type="hidden" name="__VIEWSTATE" id="__VIEWSTATE"'
        ' value="/wEPDwUKLTMyNjg0MDc1MWQYAQUeX19Db250cm9sc1JlcXVpcmVQb3'
        "N0QmFja0tleV9fFgEFIGJwJF8kY3RsMDAkXyRicyRfJHdzJF8kU2VhcmNoQm94"
        'bxUzDQVBRPB2cN8nnSmNhVZ6WX0=" />'
    )

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(
            url="http://mock/",
            body='<a href="/1">1</a>' '<a href="/2">2</a>',
            method="GET",
            status=200,
        ),
        MockResponse(
            url="http://mock/1",
            body=f"<html><body><h1>Page one</h1>{html}</body></html>",
            method="GET",
            status=200,
        ),
        MockResponse(
            url="http://mock/2",
            body=f"<html><body><h1>Page two</h1>{html}</body></html>",
            method="GET",
            status=200,
        ),
    ]

    def test_grouped_vulnerabilities(self):
        self._scan(self.target_url, RUN_CONFIGS["cfg"]["plugins"])

        vulns = self.kb.get("dot_net_event_validation", "dot_net_event_validation")

        expected_vulns = {
            (
                ".NET Event Validation is disabled",
                (
                    "The application contains 2 unique URLs which have"
                    " .NET Event Validation disabled. This programming"
                    " / configuration error should be manually"
                    " verified. The first two vulnerable URLs are:\n"
                    " - http://mock/1\n - http://mock/2\n"
                ),
            ),
            (
                ".NET ViewState encryption is disabled",
                (
                    "The application contains 2 unique URLs with .NET"
                    " ViewState encryption disabled. This programming"
                    " / configuration error can be exploited to decode"
                    " and inspect the ViewState contents. The first two"
                    " vulnerable URLs are:\n - http://mock/1\n"
                    " - http://mock/2\n"
                ),
            ),
        }

        vulns_set = set()

        for vuln in vulns:
            desc = vuln.get_desc(with_id=False)
            vulns_set.add((vuln.get_name(), desc))

        self.assertEqual(expected_vulns, vulns_set)
