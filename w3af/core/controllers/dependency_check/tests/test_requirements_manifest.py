"""Tests for the dependency checker requirements manifest."""

import unittest

from w3af.core.controllers.dependency_check import requirements


class TestRequirementsManifest(unittest.TestCase):
    def test_dependency_versions_come_from_root_manifest(self):
        self.assertEqual(
            requirements._version("PyGithub"),
            requirements.PINNED_VERSIONS["pygithub"],
        )

    def test_all_dependency_checker_packages_are_pinned(self):
        dependencies = requirements.CORE_PIP_PACKAGES + requirements.GUI_PIP_EXTRAS

        for dependency in dependencies:
            with self.subTest(package=dependency.package_name):
                self.assertEqual(
                    dependency.package_version,
                    requirements._version(dependency.package_name),
                )
