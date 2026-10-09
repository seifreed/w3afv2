"""
test_external_process.py

Copyright 2026 w3af contributors

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

import os
import sys
import tempfile
import unittest

from w3af.core.controllers.misc.external_process import (
    STDOUT,
    ExecutableNotFoundError,
    ProcessTimeoutError,
    resolve_executable,
    run_process,
    start_process,
)

PYTHON = sys.executable


class TestResolveExecutable(unittest.TestCase):
    def test_absolute_executable(self):
        self.assertEqual(resolve_executable(PYTHON), PYTHON)

    def test_absolute_path_which_is_not_executable(self):
        with tempfile.NamedTemporaryFile(suffix=".txt") as not_executable:
            self.assertRaises(
                ExecutableNotFoundError, resolve_executable, not_executable.name
            )

    def test_program_name_found_in_path(self):
        original_path = os.environ.get("PATH", "")
        self.addCleanup(os.environ.__setitem__, "PATH", original_path)
        os.environ["PATH"] = os.path.dirname(PYTHON)

        resolved = resolve_executable(os.path.basename(PYTHON))

        self.assertTrue(os.path.isabs(resolved))
        self.assertTrue(os.path.samefile(resolved, PYTHON))

    def test_program_name_missing_from_path(self):
        self.assertRaises(
            ExecutableNotFoundError, resolve_executable, "w3af-no-such-program"
        )


class TestStartProcess(unittest.TestCase):
    def test_rejects_a_command_string(self):
        self.assertRaises(TypeError, start_process, f"{PYTHON} -V")
        self.assertRaises(TypeError, start_process, b"python -V")

    def test_arguments_are_passed_verbatim(self):
        with start_process(
            [PYTHON, "-c", "import sys; print(sys.argv[1])", "$HOME; id"],
            stdout=-1,
            text=True,
        ) as process:
            out, _ = process.communicate()

        self.assertEqual(out.strip(), "$HOME; id")


class TestRunProcess(unittest.TestCase):
    def test_collects_output_and_return_code(self):
        result = run_process(
            [
                PYTHON,
                "-c",
                "import sys; print('out'); sys.stderr.write('err'); sys.exit(3)",
            ]
        )

        self.assertEqual(result.returncode, 3)
        self.assertEqual(result.stdout.strip(), "out")
        self.assertEqual(result.stderr, "err")

    def test_stderr_can_be_merged_into_stdout(self):
        result = run_process(
            [PYTHON, "-c", "import sys; sys.stderr.write('err')"],
            stderr=STDOUT,
            timeout=30,
        )

        self.assertEqual(result.stdout, "err")
        self.assertIsNone(result.stderr)

    def test_timeout_kills_the_process(self):
        with self.assertRaises(ProcessTimeoutError):
            run_process([PYTHON, "-c", "import time; time.sleep(30)"], timeout=0.5)
