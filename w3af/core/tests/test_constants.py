import unittest

from w3af.core.constants import POISON_PILL


class TestConstants(unittest.TestCase):
    def test_poison_pill_is_not_a_valid_work_item(self):
        self.assertEqual(POISON_PILL, -1)
