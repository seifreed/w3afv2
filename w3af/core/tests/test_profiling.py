import os
import unittest

from w3af.core.profiling import is_core_profiling_enabled


class TestCoreProfilingConfiguration(unittest.TestCase):
    def evaluate_with_environment(self, value):
        variable = "W3AF_CORE_PROFILING"
        previous_value = os.environ.get(variable)
        if value is None:
            os.environ.pop(variable, None)
        else:
            os.environ[variable] = value

        try:
            return is_core_profiling_enabled()
        finally:
            if previous_value is None:
                os.environ.pop(variable, None)
            else:
                os.environ[variable] = previous_value

    def test_enabled_by_one(self):
        self.assertTrue(self.evaluate_with_environment("1"))

    def test_disabled_by_zero(self):
        self.assertFalse(self.evaluate_with_environment("0"))

    def test_disabled_when_missing(self):
        self.assertFalse(self.evaluate_with_environment(None))

    def test_numeric_one_with_leading_zero_enables_profiling(self):
        self.assertTrue(self.evaluate_with_environment("01"))

    def test_disabled_by_non_numeric_values(self):
        self.assertFalse(self.evaluate_with_environment("true"))
