"""
test_special_chars.py

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

from urllib.parse import parse_qs, urlsplit

from w3af.core.controllers.tests.local_http_server import LocalHTTPServer, Reply
from w3af.plugins.tests.helper import PluginConfig, PluginTest

EVENT_VALIDATION = "bar+spam"
FORM_ACTIONS = ("/search", "/comment")

INDEX_BODY = "<html><body>{}</body></html>".format(
    "".join(
        f'<form action="{action}" method="GET">'
        f'<input name="foo" value="{EVENT_VALIDATION}" type="hidden">'
        '<input name="eggs" type="text">'
        '<input type="submit" value="Send">'
        "</form>"
        for action in FORM_ACTIONS
    )
)


def encoding_spaces_site(method: str, path: str) -> Reply:
    """
    Reflect the "eggs" parameter only when the hidden "foo" value arrives
    untouched, like a .NET EVENTVALIDATION field does.
    """
    parts = urlsplit(path)
    if parts.path not in FORM_ACTIONS:
        return Reply(body=INDEX_BODY)

    params = parse_qs(parts.query, keep_blank_values=True)
    if params.get("foo") != [EVENT_VALIDATION]:
        return Reply(body="<html><body>Invalid event validation</body></html>")

    eggs = params.get("eggs", [""])[0]
    return Reply(body=f"<html><body>You said: {eggs}</body></html>")


class TestSpecialChars(PluginTest):
    """
    This test verifies that a fix for the bug identified while scanning
    demo.testfire.net is still working as expected. The issue was that the
    site had a form that looked like:

    <form action="/xyz">
        <intput name="foo" value="bar+spam" type="hidden">
        <intput name="eggs" type="text">
        ...
    </form>

    And when trying to send a request to that form the "+" in the value
    was sent as %20. The input was an .NET's EVENTVALIDATION thus it was
    impossible to find any bugs in the "eggs" parameter.

    Please note that this is a functional test and a unittest (which does not
    verify that everything works as expected) can be found at test_form.py
    """

    def test_special_chars(self):
        site = LocalHTTPServer(encoding_spaces_site).start()
        self.addCleanup(site.close)

        plugins = {
            "audit": (PluginConfig("xss"),),
            "crawl": (
                PluginConfig(
                    "web_spider",
                    ("only_forward", True, PluginConfig.BOOL),
                ),
            ),
        }

        self._scan(site.url("/"), plugins)

        xss_vulns = self.kb.get("xss", "xss")
        self.assertEqual(len(xss_vulns), 2, xss_vulns)
