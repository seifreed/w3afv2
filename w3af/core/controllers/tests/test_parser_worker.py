"""Tests for parser worker bootstrap resources."""

import unittest

from w3af.core.controllers.output_manager import create_output_manager
from w3af.core.controllers.parser_worker import (
    get_parser_log_queue,
    initialize_parser_worker,
)


class TestParserWorker(unittest.TestCase):
    def test_active_output_manager_provides_a_log_queue(self):
        manager, _ = create_output_manager()
        self.addCleanup(manager.stop)

        self.assertIs(get_parser_log_queue(manager), manager.get_in_queue())

    def test_stopped_output_manager_does_not_provide_a_closed_queue(self):
        manager, _ = create_output_manager()
        manager.stop()

        self.assertIsNone(get_parser_log_queue(manager))

    def test_worker_without_output_manager_still_starts_profiling(self):
        initialize_parser_worker(None)
