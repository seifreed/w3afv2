import os
import unittest

from w3af.core.profiling import (
    is_core_profiling_enabled,
    is_cpu_profiling_enabled,
    is_memory_profiling_enabled,
    is_tracemalloc_enabled,
)


class TestCoreProfilingConfiguration(unittest.TestCase):
    def evaluate_with_environment(self, variable, value, predicate):
        previous_value = os.environ.get(variable)
        if value is None:
            os.environ.pop(variable, None)
        else:
            os.environ[variable] = value

        try:
            return predicate()
        finally:
            if previous_value is None:
                os.environ.pop(variable, None)
            else:
                os.environ[variable] = previous_value

    def test_enabled_by_one(self):
        self.assertTrue(
            self.evaluate_with_environment(
                "W3AF_CORE_PROFILING", "1", is_core_profiling_enabled
            )
        )

    def test_disabled_by_zero(self):
        self.assertFalse(
            self.evaluate_with_environment(
                "W3AF_CORE_PROFILING", "0", is_core_profiling_enabled
            )
        )

    def test_disabled_when_missing(self):
        self.assertFalse(
            self.evaluate_with_environment(
                "W3AF_CORE_PROFILING", None, is_core_profiling_enabled
            )
        )

    def test_numeric_one_with_leading_zero_enables_profiling(self):
        self.assertTrue(
            self.evaluate_with_environment(
                "W3AF_CORE_PROFILING", "01", is_core_profiling_enabled
            )
        )

    def test_disabled_by_non_numeric_values(self):
        self.assertFalse(
            self.evaluate_with_environment(
                "W3AF_CORE_PROFILING", "true", is_core_profiling_enabled
            )
        )

    def test_cpu_profiling_setting(self):
        self.assertTrue(
            self.evaluate_with_environment(
                "W3AF_CPU_PROFILING", "1", is_cpu_profiling_enabled
            )
        )

    def test_memory_profiling_setting(self):
        self.assertTrue(
            self.evaluate_with_environment(
                "W3AF_MEMORY_PROFILING", "1", is_memory_profiling_enabled
            )
        )

    def test_tracemalloc_setting(self):
        self.assertTrue(
            self.evaluate_with_environment(
                "W3AF_PYTRACEMALLOC", "1", is_tracemalloc_enabled
            )
        )
