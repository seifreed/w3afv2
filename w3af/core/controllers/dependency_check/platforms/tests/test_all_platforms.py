"""
test_all_platforms.py

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

import unittest

from ..base_platform import CORE
from ..current_platform import KNOWN_PLATFORMS


class TestAllPlatforms(unittest.TestCase):
    def test_os_detection(self):
        # I really need those platform detection functions to be specific!
        results = [p.is_current_platform() for p in KNOWN_PLATFORMS]
        self.assertLessEqual(results.count(True), 1, results)

    def test_attributes(self):
        REQUIRED_ATTRS = [
            "PIP_PACKAGES",
            "SYSTEM_PACKAGES",
            "SYSTEM_NAME",
            "PKG_MANAGER_CMD",
            "PIP_CMD",
        ]

        for required_attr in REQUIRED_ATTRS:
            for platform in KNOWN_PLATFORMS:
                self.assertTrue(hasattr(platform, required_attr))

    def test_core_deps(self):
        for platform in KNOWN_PLATFORMS:
            self.assertEqual(list(platform.PIP_PACKAGES), [CORE])
            self.assertEqual(list(platform.SYSTEM_PACKAGES), [CORE])

    def test_more_than_three_dependencies(self):
        for platform in KNOWN_PLATFORMS:
            self.assertGreater(len(platform.PIP_PACKAGES[CORE]), 3)

    def test_os_package_is_installed(self):
        for platform in KNOWN_PLATFORMS:
            with self.subTest(platform=platform.SYSTEM_NAME):
                installed = platform.os_package_is_installed("w3af-no-such-package")
                self.assertIn(installed, (False, None))

    def test_after_hook(self):
        # Just looking for exceptions
        [p.after_hook() for p in KNOWN_PLATFORMS]
