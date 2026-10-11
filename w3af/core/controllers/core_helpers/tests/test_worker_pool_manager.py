"""Tests for the worker-pool lifecycle."""

import unittest

import w3af.core.controllers.output_manager as om
from w3af.core.controllers.core_helpers.worker_pool_manager import (
    WorkerPoolManager,
)


class TestWorkerPoolManager(unittest.TestCase):
    def create_manager(self):
        return WorkerPoolManager(
            om.out,
            processes=1,
            max_queued_tasks=2,
            maxtasksperchild=1,
        )

    def test_reuses_running_pool(self):
        manager = self.create_manager()
        self.addCleanup(manager.terminate)

        pool = manager.get_pool()

        self.assertIs(manager.get_pool(), pool)

    def test_recreates_terminated_pool(self):
        manager = self.create_manager()
        self.addCleanup(manager.terminate)

        pool = manager.get_pool()
        manager.terminate()

        self.assertIsNone(manager._pool)
        self.assertIsNot(manager.get_pool(), pool)
