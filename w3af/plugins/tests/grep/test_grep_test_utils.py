"""Tests for shared grep plugin fixtures."""

import unittest

from w3af.core.data.db.dbms import create_temp_db_instance, database_context
from w3af.plugins.tests.grep import grep_test_utils


class TestGrepTestUtils(unittest.TestCase):
    def test_parser_cache_is_recreated_after_database_changes(self):
        previous_cache = grep_test_utils.TEST_PARSER_CACHE
        database = create_temp_db_instance()

        try:
            with database_context(database):
                grep_test_utils._refresh_parser_cache()
                self.assertIsNot(previous_cache, grep_test_utils.TEST_PARSER_CACHE)
        finally:
            database.close()
