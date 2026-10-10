import sys
import unittest

from w3af.core.controllers.dependency_check.platforms.package_query import (
    query_package,
)


def classify(output, package_name):
    if f"{package_name} is installed" in output:
        return True

    if f"{package_name} is absent" in output:
        return False

    return None


def python_reporting(report):
    """
    A real process (the running interpreter) that prints a report that ends
    with the package name it receives as last argument.
    """
    program = f"import sys; print({report!r}.format(sys.argv[-1]))"
    return (sys.executable, "-c", program)


class TestQueryPackage(unittest.TestCase):
    def test_package_name_is_appended_to_the_command(self):
        command = python_reporting("{} is installed")

        self.assertTrue(query_package(command, "libfoo", classify))

    def test_output_is_classified_by_the_caller_function(self):
        command = python_reporting("{} is absent")

        self.assertFalse(query_package(command, "libfoo", classify))

    def test_unknown_answer_is_none(self):
        command = python_reporting("what is {}?")

        self.assertIsNone(query_package(command, "libfoo", classify))

    def test_missing_package_manager_is_none(self):
        command = ("package-manager-that-is-not-installed", "-q")

        self.assertIsNone(query_package(command, "libfoo", classify))
