import shlex
import subprocess
import sys
import unittest

import pytest


@pytest.mark.smoke
class TestDependenciesInstalled(unittest.TestCase):

    def test_dependencies_installed(self):
        DEPS_CMD = (
            "%s -c 'from w3af.core.controllers.dependency_check."
            "dependency_check import dependency_check; dependency_check()'"
        )
        try:
            subprocess.check_output(shlex.split(DEPS_CMD % sys.executable))
        except subprocess.CalledProcessError as cpe:
            self.assertEqual(False, True, cpe.output)
