"""
test_zone_h.py

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

from w3af.core.data.constants import severity
from w3af.core.data.kb.vuln import Vuln
from w3af.plugins.infrastructure.zone_h import zone_h
from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest

ARCHIVE_PAGE = """<html><body>
<div id="archive">
Total notifications: <b>%s</b> of which <b>%s</b> single ip and <b>%s</b> mass
</div>
</body></html>"""

NOTIFICATIONS_BY_DOMAIN = {
    "defaced-often.com": (5, 3, 2),
    "defaced-once.com": (1, 1, 0),
    "never-defaced.com": (0, 0, 0),
}


def zone_h_archive(mock_response, request, uri, response_headers):
    response_headers["Content-Type"] = "text/html"
    domain = uri.rsplit("domain=", 1)[1]

    if domain not in NOTIFICATIONS_BY_DOMAIN:
        return 200, response_headers, "<html><body>Under maintenance</body></html>"

    return 200, response_headers, ARCHIVE_PAGE % NOTIFICATIONS_BY_DOMAIN[domain]


class TestZoneH(PluginTest):

    target_url = "http://www.defaced-often.com/"

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(
            re.compile(re.escape(zone_h.ZONE_H_ARCHIVE_URL) + ".*"),
            body=zone_h_archive,
        ),
    ]

    plugins: ClassVar[dict] = {"infrastructure": (PluginConfig("zone_h"),)}

    def scan_defacements(self, target):
        self._scan(target, self.plugins)
        return self.kb.get("zone_h", "defacements")

    def test_zone_h_defaced_more_than_once(self):
        defacements = self.scan_defacements("http://www.defaced-often.com/")

        self.assertEqual(len(defacements), 1, defacements)

        vuln = defacements[0]
        self.assertIsInstance(vuln, Vuln)
        self.assertEqual(vuln.get_name(), "Previous defacements")
        self.assertEqual(vuln.get_severity(), severity.MEDIUM)
        self.assertEqual(
            vuln.get_url().url_string,
            "http://www.zone-h.org/archive/domain=defaced-often.com",
        )
        self.assertTrue(
            vuln.get_desc().startswith("The target site was defaced more than")
        )

    def test_zone_h_defaced_once(self):
        defacements = self.scan_defacements("http://www.defaced-once.com/")

        self.assertEqual(len(defacements), 1, defacements)

        info = defacements[0]
        self.assertNotIsInstance(info, Vuln)
        self.assertEqual(info.get_name(), "Previous defacements")
        self.assertTrue(
            info.get_desc().startswith("The target site was defaced in the past")
        )

    def test_zone_h_never_defaced(self):
        defacements = self.scan_defacements("http://www.never-defaced.com/")

        self.assertEqual(defacements, [])

    def test_zone_h_unexpected_page_format(self):
        defacements = self.scan_defacements("http://www.unknown-site.com/")

        self.assertEqual(defacements, [])

    def test_long_description(self):
        self.assertIn("zone-h.org", zone_h().get_long_desc())
