"""Tests for the dependency checker requirements manifest."""

import unittest

from w3af.core.controllers.dependency_check import requirements
from w3af.core.controllers.dependency_check.dependency_check import (
    get_missing_pip_packages,
)
from w3af.core.controllers.dependency_check.platforms.current_platform import (
    get_current_platform,
)


class TestRequirementsManifest(unittest.TestCase):
    def test_dependency_versions_come_from_root_manifest(self):
        self.assertEqual(
            requirements._version("PyGithub"),
            requirements.PINNED_VERSIONS["pygithub"],
        )

    def test_all_dependency_checker_packages_are_pinned(self):
        for dependency in requirements.CORE_PIP_PACKAGES:
            with self.subTest(package=dependency.package_name):
                self.assertEqual(
                    dependency.package_version,
                    requirements._version(dependency.package_name),
                )

    def test_git_dependency_is_pinned_to_manifest_commit(self):
        dependency = next(
            dependency
            for dependency in requirements.CORE_PIP_PACKAGES
            if dependency.package_name == "mitmproxy"
        )
        self.assertEqual(
            dependency.package_version,
            "5253dcbd1d8f0522de097bfe56918fe12a0f267a",
        )
        self.assertEqual(
            dependency.git_src,
            "git+https://github.com/mitmproxy/mitmproxy.git@"
            "5253dcbd1d8f0522de097bfe56918fe12a0f267a",
        )

    def test_installed_git_dependency_matches_pinned_commit(self):
        missing_dependencies = get_missing_pip_packages(
            get_current_platform(), requirements.CORE
        )
        self.assertFalse(
            any(
                dependency.package_name == "mitmproxy"
                for dependency in missing_dependencies
            )
        )
