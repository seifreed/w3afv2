import os
import unittest

from w3af.core.environment import is_running_on_ci


class TestCiEnvironment(unittest.TestCase):
    def evaluate_with_environment(self, value):
        variable = "CIRCLECI"
        previous_value = os.environ.get(variable)
        if value is None:
            os.environ.pop(variable, None)
        else:
            os.environ[variable] = value

        try:
            return is_running_on_ci()
        finally:
            if previous_value is None:
                os.environ.pop(variable, None)
            else:
                os.environ[variable] = previous_value

    def test_true_value_enables_ci_mode(self):
        self.assertTrue(self.evaluate_with_environment("true"))

    def test_other_values_disable_ci_mode(self):
        self.assertFalse(self.evaluate_with_environment("false"))
        self.assertFalse(self.evaluate_with_environment("TRUE"))
        self.assertFalse(self.evaluate_with_environment(None))
