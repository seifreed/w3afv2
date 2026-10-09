import unittest

from w3af.core.data.misc.decorators import Memoized


class TestMemoized(unittest.TestCase):
    def test_caches_function_results(self):
        calls = []

        @Memoized
        def calculate(value):
            calls.append(value)
            return value * 2

        self.assertEqual(calculate(3), 6)
        self.assertEqual(calculate(3), 6)
        self.assertEqual(calls, [3])

    def test_binds_methods_and_keeps_instances_separate(self):
        class Counter:
            def __init__(self):
                self.calls = 0

            @Memoized
            def value(self):
                self.calls += 1
                return self.calls

        first = Counter()
        second = Counter()

        self.assertEqual(first.value(), 1)
        self.assertEqual(first.value(), 1)
        self.assertEqual(second.value(), 1)
        self.assertEqual(first.calls, 1)
        self.assertEqual(second.calls, 1)

    def test_evicts_least_recently_used_result(self):
        calls = []

        def calculate(value):
            calls.append(value)
            return value

        memoized = Memoized(calculate, lru_size=1)

        memoized(1)
        memoized(2)
        memoized(1)

        self.assertEqual(calls, [1, 2, 1])

    def test_repr_uses_wrapped_function_docstring(self):
        def calculate():
            """calculation documentation"""

        self.assertEqual(repr(Memoized(calculate)), "calculation documentation")
