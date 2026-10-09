"""Tests for traceback metadata helpers."""

import unittest
from pathlib import Path

from w3af.core.traceback_utils import get_exception_location, get_traceback


def raise_test_exception():
    raise ValueError("traceback test")


class TestTracebackUtils(unittest.TestCase):
    def test_get_traceback_returns_active_exception_traceback(self):
        try:
            raise_test_exception()
        except ValueError as error:
            traceback = get_traceback()
            caught_traceback = error.__traceback__

        self.assertIsNotNone(traceback)
        self.assertIs(traceback, caught_traceback)

    def test_get_exception_location_returns_deepest_frame_details(self):
        try:
            raise_test_exception()
        except ValueError:
            location = get_exception_location(get_traceback())

        path, filename, function_name, line_number = location
        self.assertEqual(Path(path), Path(__file__).parent)
        self.assertEqual(filename, Path(__file__).name)
        self.assertEqual(function_name, "raise_test_exception()")
        self.assertGreater(line_number, 0)

    def test_get_exception_location_returns_empty_values_without_traceback(self):
        self.assertEqual(
            get_exception_location(None),
            (None, None, None, None),
        )
