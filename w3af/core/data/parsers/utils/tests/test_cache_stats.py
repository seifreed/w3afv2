import unittest

from w3af.core.data.parsers.utils.cache_stats import CacheStats


class DebugCacheStats(CacheStats):
    CACHE_SIZE = 4
    DEBUG = True


class TestCacheStats(unittest.TestCase):
    def test_debug_records_and_cache_counters(self):
        stats = DebugCacheStats()
        stats._cache = {}

        with self.assertLogs(
            "w3af.core.data.parsers.utils.cache_stats", level="DEBUG"
        ) as records:
            stats.inc_query_count()
            stats._handle_cache_hit("hit")
            stats._handle_cache_miss("miss")
            stats._handle_no_cache("excluded")

        self.assertEqual(
            [record.getMessage() for record in records.records],
            [
                "[cache] Hit for hit",
                "[cache] Miss for miss",
                "[cache] DO NOT CACHE excluded",
            ],
        )
        self.assertEqual(stats.get_hit_rate(), 1.0)
        self.assertEqual(stats.get_max_lru_items(), 4)
        self.assertEqual(stats.get_current_lru_items(), 0)
        self.assertEqual(stats.get_total_queries(), 1)
        self.assertEqual(stats.get_do_not_cache(), 1)
        self.assertIsNone(CacheStats().get_hit_rate())
