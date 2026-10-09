"""Tests for the bloom filter wrapper API used by the scan consumers."""

import os
import unittest

from w3af.core.data.bloomfilter.bloomfilter import BloomFilter
from w3af.core.data.bloomfilter.scalable_bloom import ScalableBloomFilter
from w3af.core.data.bloomfilter.seekfile_bloom import FileSeekBloomFilter
from w3af.core.data.bloomfilter.wrappers import GenericBloomFilter
from w3af.core.filesystem import get_temp_dir


class TestScalableBloomFilterAPI(unittest.TestCase):
    def test_invalid_error_rate(self):
        self.assertRaises(ValueError, ScalableBloomFilter, error_rate=0)
        self.assertRaises(ValueError, ScalableBloomFilter, error_rate=-0.1)

    def test_add_reports_new_keys_only(self):
        bloom = ScalableBloomFilter(initial_capacity=10)

        self.assertTrue(bloom.add("a"))
        self.assertFalse(bloom.add("a"))
        self.assertEqual(bloom.count, 1)
        self.assertEqual(len(bloom), 1)

    def test_grows_when_capacity_is_reached(self):
        bloom = ScalableBloomFilter(
            initial_capacity=10, mode=ScalableBloomFilter.SMALL_SET_GROWTH
        )

        for i in range(11):
            bloom.add(str(i))

        self.assertEqual(len(bloom.filters), 2)
        self.assertEqual(bloom.capacity, 10 + 20)


class TestBloomFilterWrapper(unittest.TestCase):
    def test_repr(self):
        bloom = BloomFilter(10, 0.01)
        bloom.add("a")

        self.assertEqual(
            repr(bloom), "<BloomFilter items=1 capacity=10 error_rate=0.01>"
        )
        self.assertEqual(
            str(bloom.bf),
            "<FileSeekBloomFilter items=1 capacity=10 error_rate=0.01>",
        )

    def test_temp_file_lives_in_process_temp_dir(self):
        temp_file = GenericBloomFilter.get_temp_file()

        self.assertEqual(os.path.dirname(temp_file), get_temp_dir())
        self.assertTrue(temp_file.endswith("-w3af.bloom"))


class TestFileSeekBloomFilterClose(unittest.TestCase):
    def test_close_removes_backing_file(self):
        temp_file = GenericBloomFilter.get_temp_file()
        bloom = FileSeekBloomFilter(10, 0.01, temp_file)
        bloom.add("a")

        bloom.close()

        self.assertFalse(os.path.exists(temp_file))
