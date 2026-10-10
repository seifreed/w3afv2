"""
test_os_commanding.py

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

from w3af.plugins.tests.audit.vulnerable_responses import (
    ETC_USERS_FILE,
    html_page,
    request_param,
    sleep_for_payload,
)
from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest

OSC_URL = "http://mock/audit/os_commanding/"

INDEX_BODY = """
<a href="trivial_osc.py?cmd=ls">Trivial</a>
<a href="param_osc.py?param=-la">Parameter</a>
<a href="blind_osc.py?cmd=ls">Blind</a>
<a href="safe_osc.py?cmd=ls">Safe</a>
"""

COMMAND_SEPARATOR = r"(;|\||&&|\n|`)"
CAT_USERS_FILE = "/bin/cat /etc/passwd"
PING_DELAY = r"^ping -c (\d+) localhost$"


def run_command(command):
    if command.startswith(CAT_USERS_FILE):
        return ETC_USERS_FILE
    return "index.html\nstyle.css"


def trivial_osc(mock_response, request, uri, response_headers):
    """Run the cmd parameter as a shell command and print the output."""
    output = run_command(request_param(request, "cmd"))
    return html_page(response_headers, f"<pre>{output}</pre>")


def param_osc(mock_response, request, uri, response_headers):
    """Append the param parameter to ls, a separator runs a second command."""
    commands = re.split(COMMAND_SEPARATOR, request_param(request, "param"))
    output = "".join(run_command(command.strip()) for command in commands[1:])
    return html_page(response_headers, f"<pre>index.html {output}</pre>")


def blind_osc(mock_response, request, uri, response_headers):
    """Run the cmd parameter as a shell command without printing the output."""
    sleep_for_payload(request_param(request, "cmd"), PING_DELAY)
    return html_page(response_headers, "Command executed")


def safe_osc(mock_response, request, uri, response_headers):
    return html_page(response_headers, "Listing files is disabled")


class TestOSCommanding(PluginTest):

    target_url = OSC_URL

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(OSC_URL, INDEX_BODY),
        MockResponse(re.compile(f"{OSC_URL}trivial_osc.py.*"), trivial_osc),
        MockResponse(re.compile(f"{OSC_URL}param_osc.py.*"), param_osc),
        MockResponse(re.compile(f"{OSC_URL}blind_osc.py.*"), blind_osc),
        MockResponse(re.compile(f"{OSC_URL}safe_osc.py.*"), safe_osc),
    ]

    _run_configs: ClassVar[dict] = {
        "cfg": {
            "target": target_url,
            "plugins": {
                "audit": (PluginConfig("os_commanding"),),
                "crawl": (
                    PluginConfig(
                        "web_spider", ("only_forward", True, PluginConfig.BOOL)
                    ),
                ),
            },
        }
    }

    def test_found_osc(self):
        cfg = self._run_configs["cfg"]
        self._scan(cfg["target"], cfg["plugins"])

        vulns = self.kb.get("os_commanding", "os_commanding")

        EXPECTED = [
            ("trivial_osc.py", "cmd"),
            ("param_osc.py", "param"),
            ("blind_osc.py", "cmd"),
        ]

        self.assertAllVulnNamesEqual("OS commanding vulnerability", vulns)
        self.assertExpectedVulnsFound(EXPECTED, vulns)

        found = {v.get_url().get_file_name(): v for v in vulns}
        self.assertEqual("unix", found["trivial_osc.py"]["os"])
        self.assertEqual("", found["trivial_osc.py"]["separator"])
        self.assertIn(found["param_osc.py"]["separator"], (";", "|", "&&", "\n", "`"))
        self.assertEqual("unix", found["blind_osc.py"]["os"])
