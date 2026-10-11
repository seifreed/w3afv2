import unittest
from concurrent.futures import ThreadPoolExecutor

from w3af.core.data.misc.number_generator import NumberGenerator
from w3af.core.data.misc.serialize import dumps, loads


class TestNumberGenerator(unittest.TestCase):

    def setUp(self):
        self.generator = NumberGenerator()

    def test_increment_returns_next_number(self):
        self.assertEqual(self.generator.inc(), 1)
        self.assertEqual(self.generator.inc(), 2)

    def test_get_returns_current_number(self):
        self.generator.inc()

        self.assertEqual(self.generator.get(), 1)

    def test_reset_starts_sequence_over(self):
        self.generator.inc()
        self.generator.reset()

        self.assertEqual(self.generator.get(), 0)
        self.assertEqual(self.generator.inc(), 1)

    def test_concurrent_increments_are_unique(self):
        def increment(_):
            return self.generator.inc()

        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(increment, range(200)))

        self.assertEqual(sorted(results), list(range(1, 201)))
        self.assertEqual(self.generator.get(), 200)

    def test_serialization_restores_the_lock_and_counter(self):
        self.generator.inc()

        restored = loads(dumps(self.generator))

        self.assertEqual(restored.get(), 1)
        self.assertEqual(restored.inc(), 2)
