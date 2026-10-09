"""
test_dependency_check.py

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

import io
import unittest
from contextlib import redirect_stdout

from ..dependency_check import dependency_check
from ..pip_dependency import PIPDependency
from ..platforms.base_platform import CORE
from ..platforms.default import DefaultPlatform
from ..platforms.ubuntu1204 import Ubuntu1204


class TestDependencyCheck(unittest.TestCase):

    MISSING_DEP_CMD = "pip install rumbamanager==3.2.1"

    def setUp(self):
        self.fake_rumba_dependency = PIPDependency(
            "rumbamanager", "rumbamanager", "3.2.1"
        )

    def test_works_at_this_workstation(self):
        """
        Test that the dependency check works well @ this system
        """
        must_exit = dependency_check(dependency_set=CORE, exit_on_failure=False)
        self.assertFalse(must_exit)

    def test_default_platform_core_all_deps(self):
        """
        Test that the dependency check works for core + default platform when
        the dependencies are met.
        """
        must_exit = dependency_check(
            dependency_set=CORE, exit_on_failure=False, platform=DefaultPlatform()
        )
        self.assertFalse(must_exit)

    def test_default_platform_core_missing_deps(self):
        """
        Test that the dependency check works for core + default platform when
        there are missing PIP core dependencies.
        """
        default = DefaultPlatform()
        default.PIP_PACKAGES = default.PIP_PACKAGES.copy()
        default.PIP_PACKAGES[CORE] = default.PIP_PACKAGES[CORE][:]
        default.PIP_PACKAGES[CORE].append(self.fake_rumba_dependency)

        console_output = io.StringIO()
        with redirect_stdout(console_output):
            must_exit = dependency_check(
                dependency_set=CORE, exit_on_failure=False, platform=default
            )

        self.assertTrue(must_exit)
        self.assertIn(self.MISSING_DEP_CMD, console_output.getvalue())

    def test_ubuntu1204_core(self):
        """
        Test that the dependency check works for core + ubuntu1204
        """
        must_exit = dependency_check(
            dependency_set=CORE, exit_on_failure=False, platform=Ubuntu1204()
        )
        self.assertFalse(must_exit)
