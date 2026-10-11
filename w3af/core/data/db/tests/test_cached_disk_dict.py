"""
test_cached_disk_dict.py

Copyright 2018 Andres Riancho

This file is part of w3af, http://w3af.org/ .

w3af is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation version 2 of the License.

w3af is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with w3af; if not, write to the Free Software
Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

"""

import unittest

from w3af.core.data.db.cached_disk_dict import CachedDiskDict


class TestCachedDiskDict(unittest.TestCase):
    def setUp(self):
        self.cdd = CachedDiskDict(max_in_memory=3)

    def tearDown(self):
        self.cdd.cleanup()

    def test_simple_all_in_memory(self):
        self.cdd[1] = 6789
        self.cdd[2] = None
        self.cdd[3] = None

        self.assertEqual(len(self.cdd._disk_dict), 0)
        self.assertEqual(len(self.cdd._in_memory), 3)
        self.assertEqual(self.cdd._access_count, {1: 1, 2: 1, 3: 1})
        self.assertEqual(self.cdd._in_memory, {1: 6789, 2: None, 3: None})

        self.assertEqual(self.cdd[1], 6789)

    def test_one_in_disk(self):
        self.cdd[1] = 6789
        self.cdd[2] = None
        self.cdd[3] = None

        self.cdd[1] = 6789
        self.cdd[2] = None
        self.cdd[3] = None

        self.cdd[4] = 9876

        self.assertEqual(self.cdd._access_count, {1: 2, 2: 2, 3: 2, 4: 1})
        self.assertEqual(sorted(self.cdd._in_memory.keys()), [1, 2, 3])
        self.assertEqual(sorted(self.cdd._disk_dict.keys()), [4])
        self.assertEqual(self.cdd[1], 6789)
        self.assertEqual(self.cdd[4], 9876)

    def test_one_in_disk_then_moves_to_memory(self):
        self.cdd[1] = 6789
        self.cdd[2] = None
        self.cdd[3] = None

        self.cdd[1] = 6789
        self.cdd[2] = None
        self.cdd[3] = None

        self.cdd[4] = 9876

        self.assertEqual(sorted(self.cdd._in_memory.keys()), [1, 2, 3])
        self.assertEqual(sorted(self.cdd._disk_dict.keys()), [4])
        self.assertEqual(self.cdd[1], 6789)
        self.assertEqual(self.cdd._access_count, {1: 3, 2: 2, 3: 2, 4: 1})

        self.cdd[4]
        self.cdd[4]
        self.cdd[4]

        self.assertEqual(self.cdd._access_count, {1: 3, 2: 2, 3: 2, 4: 4})

        self.assertEqual(sorted(self.cdd._in_memory.keys()), [1, 2, 4])
        self.assertEqual(sorted(self.cdd._disk_dict.keys()), [3])
        self.assertEqual(self.cdd[4], 9876)

    def test_one_in_disk_then_moves_to_memory_then_disk_again(self):
        self.cdd[1] = 1
        self.cdd[2] = 2
        self.cdd[3] = 3

        self.cdd[1] = 1
        self.cdd[2] = 2
        self.cdd[3] = 3

        self.cdd[4] = 4

        self.assertEqual(sorted(self.cdd._in_memory.keys()), [1, 2, 3])
        self.assertEqual(sorted(self.cdd._disk_dict.keys()), [4])

        self.cdd[4]
        self.cdd[4]
        self.cdd[4]

        self.assertEqual(sorted(self.cdd._in_memory.keys()), [1, 2, 4])
        self.assertEqual(sorted(self.cdd._disk_dict.keys()), [3])

        self.cdd[1]
        self.cdd[1]
        self.cdd[1]

        self.cdd[3]
        self.cdd[3]
        self.cdd[3]

        self.cdd[2]
        self.cdd[2]
        self.cdd[2]

        self.assertEqual(sorted(self.cdd._in_memory.keys()), [1, 2, 3])
        self.assertEqual(sorted(self.cdd._disk_dict.keys()), [4])

        self.assertEqual([self.cdd[k] for k in (1, 2, 3, 4)], [1, 2, 3, 4])

    def test_get_default(self):
        self.cdd[1] = "one"

        self.assertEqual(self.cdd.get(1), "one")
        self.assertEqual(self.cdd.get(2, None), None)
        self.assertEqual(self.cdd.get(2, -456), -456)
        self.assertRaises(KeyError, self.cdd.get, 2)

    def test_key_already_moved_to_memory(self):
        self.cdd._access_count.update([5])

        self.cdd._move_key_to_memory_if_needed(5, [5])

        self.assertNotIn(5, self.cdd._in_memory)

    def test_table_prefix(self):
        cdd = CachedDiskDict(table_prefix="variants")
        self.addCleanup(cdd.cleanup)

        self.assertIn("cached_disk_dict_variants_", cdd._disk_dict.table_name)
