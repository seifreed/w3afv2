import unittest

from w3af.core.controllers.ci.only_ci_decorator import only_ci
from w3af.core.controllers.ci.tests.real_state import environment_variable


@only_ci
def add_numbers(left, right):
    """Documented adder."""
    return left + right


class TestOnlyCi(unittest.TestCase):
    def test_runs_the_function_on_ci(self):
        with environment_variable("CIRCLECI", "true"):
            self.assertEqual(add_numbers(2, right=3), 5)

    def test_skips_the_function_outside_ci(self):
        with environment_variable("CIRCLECI", None):
            self.assertIsNone(add_numbers(2, 3))

    def test_preserves_function_metadata(self):
        self.assertEqual(add_numbers.__name__, "add_numbers")
        self.assertEqual(add_numbers.__doc__, "Documented adder.")
