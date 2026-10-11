"""
test_sql_identifier.py

Copyright 2026 w3af contributors

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
from w3af.core.data.db.dbms import get_default_temp_db_instance
from w3af.core.data.db.history import HistoryItem
from w3af.core.data.db.sql_identifier import require_safe_identifier
from w3af.core.filesystem import create_temp_dir


class TestRequireSafeIdentifier(unittest.TestCase):
    def test_internal_identifiers_are_accepted(self):
        for name in ("history_items", "disk_dict_abc", "Table1"):
            self.assertEqual(require_safe_identifier(name), name)

    def test_unsafe_identifiers_are_rejected(self):
        for name in ("", "a b", "x; DROP TABLE y", "name--", "t.c", None, 1):
            with self.assertRaisesRegex(ValueError, "Unsafe SQL identifier"):
                require_safe_identifier(name)

    def test_history_search_rejects_unsafe_columns(self):
        create_temp_dir()
        history = HistoryItem(db=get_default_temp_db_instance())
        history.init()
        self.addCleanup(history.clear)

        with self.assertRaisesRegex(ValueError, "Unsafe SQL identifier"):
            history.find([("id = 1 OR 1", 1, "=")])


class TestCachedDiskDictArguments(unittest.TestCase):
    def test_memory_size_must_be_positive(self):
        for size in (0, -1):
            with self.assertRaisesRegex(ValueError, "must be > 0"):
                CachedDiskDict(max_in_memory=size)
