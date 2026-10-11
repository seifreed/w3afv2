"""Tests for the resources assembled for a scan core."""

import unittest

from w3af.core.controllers.core_helpers.core_resource_factory import (
    CoreResourceFactory,
)
from w3af.core.data.kb.knowledge_base import DBKnowledgeBase


class TestCoreResourceFactory(unittest.TestCase):
    def setUp(self):
        self.factory = CoreResourceFactory(1, 2, 3)

    def test_create_owns_a_new_database(self):
        resources = self.factory.create()
        self.addCleanup(resources.resource_lifecycle.stop)
        resources.knowledge_base.setup()

        self.assertTrue(resources.owns_database)
        self.assertIs(resources.database, resources.knowledge_base.db)

    def test_create_preserves_an_injected_database(self):
        knowledge_base = DBKnowledgeBase()
        self.addCleanup(knowledge_base.cleanup)

        resources = self.factory.create(knowledge_base)
        self.addCleanup(resources.resource_lifecycle.stop)

        self.assertFalse(resources.owns_database)
        self.assertIs(resources.knowledge_base, knowledge_base)
        self.assertIs(resources.database, knowledge_base.db)
