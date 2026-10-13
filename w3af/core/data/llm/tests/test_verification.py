"""Validation tests for generated verification responses."""

import unittest

from w3af.core.data.db.dbms import create_temp_db_instance
from w3af.core.data.kb.config import Config
from w3af.core.data.llm.providers import LLMProviderError
from w3af.core.data.llm.verification import LLMVerificationService


class VerificationTest(unittest.TestCase):
    def setUp(self):
        database = create_temp_db_instance()
        self.addCleanup(database.close)
        self.service = LLMVerificationService(database, None, Config())
        self.addCleanup(self.service.shutdown)

    def test_parse_json_with_markdown_wrapper(self):
        result = self.service._parse_answer('```json {"poc": []} ```')
        self.assertEqual(result, {"poc": []})

    def test_parse_json_requires_poc_list(self):
        with self.assertRaises(LLMProviderError):
            self.service._parse_answer("not json")
        with self.assertRaises(LLMProviderError):
            self.service._parse_answer('{"poc": {}}')
