"""
test_w3af_console.py

Copyright 2012 Andres Riancho

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

import subprocess
import sys
import unittest

from w3af.core.data.db.startup_cfg import StartUpConfig
from w3af.tests.helpers.home_dir import use_temporary_home


class TestW3afConsole(unittest.TestCase):
    def setUp(self):
        # w3af_console inherits the temporary home through the environment
        use_temporary_home(self)

    def test_compiles(self):
        with open("w3af_console") as console_script:
            compile(console_script.read(), "w3af_console", "exec")

    def test_get_prompt(self):
        # We want to get the prompt, not a disclaimer message, and we must not
        # depend on this machine's third-party dependencies being installed:
        # skip-dependencies-check makes w3af_console start deterministically.
        startup_cfg = StartUpConfig()
        startup_cfg.accepted_disclaimer = True
        startup_cfg.skip_dependencies_check = True
        startup_cfg.save()

        # The easy way to do this was to simply pass 'python' to Popen
        # but now that we want to run the tests in virtualenv, we need to
        # find the "correct" / "virtual" python executable using which and
        # then pass that one to Popen
        python_executable = sys.executable

        p = subprocess.Popen(
            [python_executable, "w3af_console", "-n"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE,
            shell=False,
            universal_newlines=True,
        )

        expected_prompt = "w3af>>>"

        stdout, _stderr = p.communicate("exit\r\n")

        msg = 'Failed to find "%s" in "%s" using "%s" as python executable.'
        msg = msg % (expected_prompt, stdout, python_executable)
        self.assertIn(expected_prompt, stdout, msg)
