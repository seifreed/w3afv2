"""
test_helper_requirements_txt.py

Copyright 2013 Andres Riancho

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

from w3af.core.controllers.dependency_check.helper_requirements_txt import (
    generate_requirements_txt,
)
from w3af.core.controllers.dependency_check.pip_dependency import PIPDependency


class TestGenerateTXT(unittest.TestCase):

    def setUp(self):
        self.original_ci = os.environ.get("CIRCLECI")
        os.environ["CIRCLECI"] = "true"
        self.temp_directory = tempfile.TemporaryDirectory()
        self.original_directory = os.getcwd()
        os.chdir(self.temp_directory.name)

    def tearDown(self):
        os.chdir(self.original_directory)
        self.temp_directory.cleanup()
        if self.original_ci is None:
            os.environ.pop("CIRCLECI", None)
        else:
            os.environ["CIRCLECI"] = self.original_ci

    def test_generate_requirements_txt_empty(self):
        with open("requirements.txt", "w") as requirements_file:
            requirements_file.write("project==1.0\n")

        generated_file = generate_requirements_txt([])

        with open(generated_file) as requirements_file:
            self.assertEqual("", requirements_file.read())
        with open("requirements.txt") as requirements_file:
            self.assertEqual("project==1.0\n", requirements_file.read())

    def test_generate_requirements_txt(self):
        expected = "a==1.2.3\nc==3.2.1\n"
        dependencies = [
            PIPDependency("a", "a", "1.2.3"),
            PIPDependency("b", "c", "3.2.1"),
        ]

        generated_file = generate_requirements_txt(dependencies)

        with open(generated_file) as requirements_file:
            self.assertEqual(expected, requirements_file.read())
