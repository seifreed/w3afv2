import sys
import unittest

from w3af.core.controllers.dependency_check.external.retirejs import (
    is_supported_version,
    retirejs_is_installed,
)


def python_printing(output, exit_code=0):
    """
    A real process (the running interpreter) that writes the given output the
    way `retire --version` does and exits with the given code.
    """
    program = f"import sys; print({output!r}); sys.exit({exit_code})"
    return (sys.executable, "-c", program)


class TestIsSupportedVersion(unittest.TestCase):
    def test_supported_versions(self):
        for version in ("2.0.3", "2.6.0\n", "  2.2.5  "):
            with self.subTest(version=version):
                self.assertTrue(is_supported_version(version))

    def test_unsupported_versions(self):
        for version in ("1.6.0", "3.0.0", "2.0", "2.0.3.1", "", "retire 2.0.3"):
            with self.subTest(version=version):
                self.assertFalse(is_supported_version(version))


class TestRetirejsIsInstalled(unittest.TestCase):
    def test_supported_version_is_installed(self):
        self.assertTrue(retirejs_is_installed(python_printing("2.0.3")))

    def test_old_version_is_not_accepted(self):
        self.assertFalse(retirejs_is_installed(python_printing("1.6.0")))

    def test_failing_command_is_not_installed(self):
        self.assertFalse(retirejs_is_installed(python_printing("2.0.3", 3)))

    def test_missing_program_is_not_installed(self):
        self.assertFalse(retirejs_is_installed(("retire-not-installed-here",)))
