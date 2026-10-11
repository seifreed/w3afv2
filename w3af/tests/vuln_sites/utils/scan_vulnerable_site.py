"""
test_scan_vulnerable_site.py

Copyright 2014 Andres Riancho

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

from typing import ClassVar, cast

import pytest

from w3af.plugins.tests.helper import PluginConfig, PluginTest


@pytest.mark.functional
@pytest.mark.internet
@pytest.mark.slow
@pytest.mark.ci_fails
class TestScanVulnerableSite:

    target_url: str | None = None

    _run_configs: ClassVar[dict] = {
        "cfg": {
            "plugins": {
                "crawl": (
                    PluginConfig(
                        "web_spider",
                    ),
                ),
                "audit": (PluginConfig("all"),),
                "grep": (PluginConfig("all"),),
            }
        }
    }

    EXPECTED_VULNS: ClassVar[set[tuple]] = {()}

    def test_scan_vulnerable_site(self):
        if self.target_url is None:
            return

        cfg = self._run_configs["cfg"]
        plugin_test = cast(PluginTest, self)
        plugin_test._scan(self.target_url, cfg["plugins"])

        plugin_test.assertMostExpectedVulnsFound(self.EXPECTED_VULNS)
