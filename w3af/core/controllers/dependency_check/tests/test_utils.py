import io
import sys
import unittest
from contextlib import redirect_stdout

from w3af.core.controllers.dependency_check.utils import (
    running_in_virtualenv,
    verify_pip_available,
    verify_python_version,
)


class TestVerifyPythonVersion(unittest.TestCase):
    def test_python_314_is_accepted(self):
        output = io.StringIO()

        with redirect_stdout(output):
            verify_python_version((3, 14, 2))

        self.assertEqual(output.getvalue(), "")

    def test_other_python_versions_exit_with_message(self):
        for version in ((3, 13, 1), (2, 7, 18), (3, 15, 0)):
            with self.subTest(version=version):
                output = io.StringIO()

                with redirect_stdout(output), self.assertRaises(SystemExit) as ctx:
                    verify_python_version(version)

                self.assertEqual(ctx.exception.code, 1)
                self.assertIn(
                    "Error: Python 3.14 required; found Python "
                    + ".".join(str(p) for p in version),
                    output.getvalue(),
                )

    def test_running_interpreter_is_checked_by_default(self):
        verify_python_version()


class TestVerifyPipAvailable(unittest.TestCase):
    def test_pip_is_available(self):
        verify_pip_available()

    def test_missing_pip_exits_with_instructions(self):
        output = io.StringIO()

        with redirect_stdout(output), self.assertRaises(SystemExit) as ctx:
            verify_pip_available("module_that_is_not_installed_anywhere")

        self.assertEqual(ctx.exception.code, 1)
        self.assertIn("We recommend you install pip", output.getvalue())


class TestRunningInVirtualenv(unittest.TestCase):
    def test_matches_interpreter_prefixes(self):
        self.assertEqual(running_in_virtualenv(), sys.prefix != sys.base_prefix)
