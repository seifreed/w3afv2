"""Persistence tests for verification records."""

import unittest

from w3af.core.data.db.dbms import create_temp_db_instance
from w3af.core.data.llm.storage import VerificationStorage


class VerificationStorageTest(unittest.TestCase):
    def setUp(self):
        self.database = create_temp_db_instance()
        self.addCleanup(self.database.close)
        self.storage = VerificationStorage(self.database)

    def test_create_update_and_read(self):
        self.assertTrue(self.storage.create_pending("finding-1"))
        self.storage.update(
            "finding-1",
            "confirmed",
            provider="ollama",
            model="test",
            result={"confidence": 1},
        )
        self.assertEqual(self.storage.get("finding-1")["result"], {"confidence": 1})

    def test_completed_findings_are_not_queued_twice(self):
        self.assertTrue(self.storage.create_pending("finding-1"))
        self.storage.update("finding-1", "confirmed")
        self.assertFalse(self.storage.create_pending("finding-1"))

    def test_failed_findings_can_be_retried(self):
        self.assertTrue(self.storage.create_pending("finding-1"))
        self.storage.update("finding-1", "failed", error="provider down")
        self.assertTrue(self.storage.create_pending("finding-1"))
