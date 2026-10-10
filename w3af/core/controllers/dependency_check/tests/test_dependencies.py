import sys
import unittest

import pytest

from w3af.core.controllers.misc.external_process import run_process

CHECK_DEPENDENCIES = (
    "from w3af.core.controllers.dependency_check."
    "dependency_check import dependency_check; dependency_check()"
)


@pytest.mark.smoke
class TestDependenciesInstalled(unittest.TestCase):

    def test_dependencies_installed(self):
        result = run_process([sys.executable, "-c", CHECK_DEPENDENCIES], timeout=120)

        self.assertEqual(result.returncode, 0, result.stdout)
