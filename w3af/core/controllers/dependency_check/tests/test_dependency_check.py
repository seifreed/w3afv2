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
import logging
import re
import unittest
from contextlib import redirect_stdout
from importlib.metadata import version
from pathlib import Path
from typing import ClassVar

from w3af.core.controllers.ci.tests.real_state import environment_variable
from w3af.core.data.db.startup_cfg import StartUpConfig
from w3af.tests.helpers.home_dir import use_temporary_home

from ..dependency_check import (
    dependency_check,
    get_missing_external_commands,
    get_missing_os_packages,
    get_missing_pip_packages,
    write_instructions_to_console,
)
from ..pip_dependency import PIPDependency
from ..platforms.base_platform import CORE
from ..platforms.default import DefaultPlatform

INSTALLED_DEPENDENCY = PIPDependency("pytest", "pytest", version("pytest"))
MISSING_DEPENDENCY = PIPDependency("rumbamanager", "rumbamanager", "3.2.1")
MISSING_GIT_DEPENDENCY = PIPDependency(
    "rumbagit",
    "rumbagit",
    "abc123",
    git_src="git+https://example.invalid/rumba.git@abc123",
)


class SatisfiedPlatform(DefaultPlatform):
    """A platform where every dependency can be found in this environment."""

    SYSTEM_NAME = "Test OS"
    PKG_MANAGER_CMD = "pkg install"
    PIP_PACKAGES: ClassVar[dict[int, list[PIPDependency]]] = {
        CORE: [INSTALLED_DEPENDENCY]
    }

    @staticmethod
    def get_missing_external_commands(retirejs_command=None):
        return []


class MissingPipPlatform(SatisfiedPlatform):
    PIP_PACKAGES: ClassVar[dict[int, list[PIPDependency]]] = {
        CORE: [INSTALLED_DEPENDENCY, MISSING_DEPENDENCY, MISSING_GIT_DEPENDENCY]
    }


class MissingOsPackagesPlatform(SatisfiedPlatform):
    SYSTEM_PACKAGES: ClassVar[dict[int, list[str]]] = {
        CORE: ["libfoo-dev", "libbar-dev", "libfoo-dev"]
    }


class MissingExternalCommandPlatform(SatisfiedPlatform):
    @staticmethod
    def get_missing_external_commands(retirejs_command=None):
        return ["npm install -g retire@2.0.3"]


class DependencyCheckTestCase(unittest.TestCase):
    def setUp(self):
        use_temporary_home(self)
        self.set_skip_check(False)

        self.enterContext(environment_variable("CIRCLECI", None))

    @staticmethod
    def set_skip_check(skip):
        startup_cfg = StartUpConfig()
        startup_cfg.set_skip_dependencies_check(skip)
        startup_cfg.save()

    @staticmethod
    def check(platform, exit_on_failure=False):
        output = io.StringIO()
        with redirect_stdout(output):
            result = dependency_check(
                dependency_set=CORE,
                exit_on_failure=exit_on_failure,
                platform=platform,
            )
        return result, output.getvalue()


class TestDependencyCheck(DependencyCheckTestCase):
    def test_everything_installed_does_not_require_exit(self):
        must_exit, output = self.check(SatisfiedPlatform())

        self.assertFalse(must_exit)
        self.assertEqual(output, "")

    def test_skip_configuration_disables_the_check(self):
        self.set_skip_check(True)

        must_exit, output = self.check(MissingPipPlatform())

        self.assertFalse(must_exit)
        self.assertEqual(output, "")

    def test_missing_pip_packages_are_reported_with_install_commands(self):
        must_exit, output = self.check(MissingPipPlatform())

        self.assertTrue(must_exit)
        self.assertIn("w3af's requirements are not met", output)
        self.assertIn("rumbamanager rumbagit", output)
        self.assertIn("rumbamanager==3.2.1", output)
        self.assertIn("install --ignore-installed git+https://example", output)
        self.assertNotIn("pytest==", output)

    def test_helper_script_contains_the_install_commands(self):
        _, output = self.check(MissingPipPlatform())

        script_match = re.search(r"created for you at (.*)", output)
        if script_match is None:
            raise AssertionError("Dependency check did not report its script path")
        script_path = script_match.group(1)
        script = Path(script_path).read_text()
        self.assertTrue(script.startswith("#!/bin/bash\n"))
        self.assertIn("rumbamanager==3.2.1", script)
        self.assertIn("git+https://example.invalid/rumba.git@abc123", script)

    def test_missing_os_packages_are_reported_once(self):
        must_exit, output = self.check(MissingOsPackagesPlatform())

        self.assertTrue(must_exit)
        self.assertIn("On Test OS systems please install", output)
        self.assertEqual(output.count("libfoo-dev"), 1)
        self.assertIn("libbar-dev", output)

    def test_missing_external_commands_are_reported(self):
        must_exit, output = self.check(MissingExternalCommandPlatform())

        self.assertTrue(must_exit)
        self.assertIn("External programs used by w3af are not installed", output)
        self.assertIn("    npm install -g retire@2.0.3", output)

    def test_exit_on_failure_exits_with_error_code(self):
        with self.assertRaises(SystemExit) as context:
            self.check(MissingPipPlatform(), exit_on_failure=True)

        self.assertEqual(context.exception.code, 1)

    def test_logging_and_warnings_are_restored_after_the_check(self):
        self.check(MissingPipPlatform())

        self.assertEqual(logging.root.manager.disable, logging.NOTSET)

    def test_current_platform_is_used_by_default(self):
        output = io.StringIO()
        with redirect_stdout(output):
            must_exit = dependency_check(exit_on_failure=False)

        self.assertIsInstance(must_exit, bool)
        self.assertEqual(
            must_exit, "w3af's requirements are not met" in output.getvalue()
        )


class TestGetMissingPipPackages(unittest.TestCase):
    def missing(self, *dependencies):
        platform_class = type(
            "PlatformWithDependencies",
            (DefaultPlatform,),
            {"PIP_PACKAGES": {CORE: list(dependencies)}},
        )
        return get_missing_pip_packages(platform_class(), CORE)

    def test_installed_package_with_matching_version_is_not_missing(self):
        self.assertEqual(self.missing(INSTALLED_DEPENDENCY), [])

    def test_package_name_is_compared_normalized(self):
        dependency = PIPDependency("pytest", "PyTest", version("pytest"))
        self.assertEqual(self.missing(dependency), [])

    def test_installed_package_with_other_version_is_missing(self):
        outdated = PIPDependency("pytest", "pytest", "0.0.1")
        self.assertEqual(self.missing(outdated), [outdated])

    def test_not_installed_package_is_missing(self):
        self.assertEqual(self.missing(MISSING_DEPENDENCY), [MISSING_DEPENDENCY])

    def test_git_dependency_installed_from_an_index_is_missing(self):
        # pytest has no direct_url.json: it was not installed from git
        from_git = PIPDependency(
            "pytest", "pytest", "abc123", git_src="git+https://example.invalid/x@abc"
        )
        self.assertEqual(self.missing(from_git), [from_git])

    def test_git_dependency_with_other_commit_is_missing(self):
        mitmproxy = PIPDependency(
            "mitmproxy", "mitmproxy", "0" * 40, git_src="git+https://example.invalid"
        )
        self.assertEqual(self.missing(mitmproxy), [mitmproxy])


class TestGetMissingOsAndExternal(unittest.TestCase):
    def test_default_platform_reports_no_os_packages_when_none_required(self):
        self.assertEqual(get_missing_os_packages(DefaultPlatform(), CORE), [])

    def test_os_packages_are_deduplicated(self):
        missing = get_missing_os_packages(MissingOsPackagesPlatform(), CORE)
        self.assertEqual(sorted(missing), ["libbar-dev", "libfoo-dev"])

    def test_external_commands_come_from_the_platform(self):
        self.assertEqual(
            get_missing_external_commands(MissingExternalCommandPlatform()),
            ["npm install -g retire@2.0.3"],
        )


class TestWriteInstructions(unittest.TestCase):
    def test_only_the_script_location_is_printed_when_nothing_is_missing(self):
        output = io.StringIO()

        with redirect_stdout(output):
            write_instructions_to_console(SatisfiedPlatform(), [], [], "/x/s.sh", [])

        self.assertIn(
            "A script with these commands has been created for you at /x/s.sh",
            output.getvalue(),
        )
        self.assertNotIn("Your python installation needs", output.getvalue())
