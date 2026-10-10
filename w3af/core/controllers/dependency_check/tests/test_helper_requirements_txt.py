"""
test_helper_requirements_txt.py

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

import os
import tempfile
import unittest

from w3af.core.controllers.ci.tests.real_state import environment_variable
from w3af.core.controllers.dependency_check.helper_requirements_txt import (
    REQUIREMENTS_TXT,
    generate_requirements_txt,
)
from w3af.core.controllers.dependency_check.pip_dependency import PIPDependency


class TestGenerateTXT(unittest.TestCase):

    def setUp(self):
        temp_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temp_directory.cleanup)

        original_directory = os.getcwd()
        self.addCleanup(os.chdir, original_directory)
        os.chdir(temp_directory.name)

    def test_generate_requirements_txt_empty(self):
        with open("requirements.txt", "w") as requirements_file:
            requirements_file.write("project==1.0\n")

        with environment_variable("CIRCLECI", "true"):
            generated_file = generate_requirements_txt([])

        with open(generated_file) as requirements_file:
            self.assertEqual("", requirements_file.read())
        with open("requirements.txt") as requirements_file:
            self.assertEqual("project==1.0\n", requirements_file.read())

    def test_generate_requirements_txt_without_dependencies_list(self):
        with environment_variable("CIRCLECI", "true"):
            generated_file = generate_requirements_txt(None)

        with open(generated_file) as requirements_file:
            self.assertEqual("", requirements_file.read())

    def test_generate_requirements_txt(self):
        expected = "a==1.2.3\nc==3.2.1\n"
        dependencies = [
            PIPDependency("a", "a", "1.2.3"),
            PIPDependency("b", "c", "3.2.1"),
        ]

        with environment_variable("CIRCLECI", "true"):
            generated_file = generate_requirements_txt(dependencies)

        with open(generated_file) as requirements_file:
            self.assertEqual(expected, requirements_file.read())

    def test_git_dependencies_are_written_with_their_source(self):
        dependencies = [
            PIPDependency("g", "g", "abc", git_src="git+https://example.invalid/g@abc")
        ]

        with environment_variable("CIRCLECI", "true"):
            generated_file = generate_requirements_txt(dependencies)

        with open(generated_file) as requirements_file:
            self.assertEqual(
                "git+https://example.invalid/g@abc\n", requirements_file.read()
            )

    def test_nothing_is_generated_outside_ci(self):
        with environment_variable("CIRCLECI", None):
            result = generate_requirements_txt([PIPDependency("a", "a", "1")])

        self.assertIsNone(result)
        self.assertFalse(os.path.exists(REQUIREMENTS_TXT))
