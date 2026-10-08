import unittest

from w3af.core.data.misc.lru import LRUDict, SynchronizedLRUDict


class TestLRUDict(unittest.TestCase):
    def test_lru_eviction_and_access_order(self):
        cache = LRUDict(capacity=2)
        cache["first"] = 1
        cache["second"] = 2

        self.assertEqual(cache.get("first"), 1)
        cache["third"] = 3

        self.assertNotIn("second", cache)
        self.assertEqual(cache.items(), (("first", 1), ("third", 3)))

    def test_mapping_methods_and_clear(self):
        cache = LRUDict(capacity=2)
        cache["item"] = 1

        self.assertEqual(cache["item"], 1)
        self.assertEqual(cache.keys(), ("item",))
        self.assertEqual(cache.values(), (1,))
        self.assertEqual(tuple(cache), ("item",))
        self.assertIn("item", cache)
        del cache["item"]
        cache.clear()
        self.assertEqual(len(cache), 0)

    def test_missing_values_and_invalid_capacity(self):
        cache = LRUDict()

        self.assertIsNone(cache.get("missing"))
        with self.assertRaises(KeyError):
            cache["missing"]
        with self.assertRaises(ValueError):
            LRUDict(capacity=0)

    def test_synchronized_mapping_methods(self):
        cache = SynchronizedLRUDict(capacity=2)
        cache["first"] = 1
        cache["second"] = 2

        self.assertEqual(cache.get("first"), 1)
        cache["third"] = 3

        self.assertNotIn("second", cache)
        self.assertEqual(cache.items(), (("first", 1), ("third", 3)))
        self.assertEqual(cache.keys(), ("first", "third"))
        self.assertEqual(cache.values(), (1, 3))
        self.assertEqual(tuple(cache), ("first", "third"))
        self.assertEqual(len(cache), 2)
        del cache["first"]
        cache.clear()
        self.assertEqual(len(cache), 0)
