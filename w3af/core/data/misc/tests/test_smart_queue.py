"""
test_smart_queue.py

Copyright 2015 Andres Riancho

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

import time
import unittest

from w3af.core.data.misc.smart_queue import QueueSpeedMeasurement


def spaced_timestamps(count, seconds_between):
    """
    :return: `count` timestamps ending now, `seconds_between` seconds apart
    """
    now = time.time()
    return [now - seconds_between * (count - 1 - i) for i in range(count)]


class TestQueueSpeedMeasurement(unittest.TestCase):
    def test_no_data(self):
        measurement = QueueSpeedMeasurement()

        self.assertEqual(measurement.get_input_rpm(), 0.0)
        self.assertEqual(measurement.get_output_rpm(), 0.0)

    def test_items_are_recorded(self):
        measurement = QueueSpeedMeasurement()

        measurement._item_added_to_queue()
        measurement._item_added_to_queue()
        measurement._item_left_queue()

        self.assertEqual(len(measurement._input_timestamps), 2)
        self.assertEqual(len(measurement._output_timestamps), 1)

    def test_input_and_output_rpm(self):
        measurement = QueueSpeedMeasurement()
        measurement._input_timestamps = spaced_timestamps(4, 3)
        measurement._output_timestamps = spaced_timestamps(4, 1)

        self.assertAlmostEqual(measurement.get_input_rpm(), 20, places=3)
        self.assertAlmostEqual(measurement.get_output_rpm(), 60, places=3)

    def test_old_samples_are_ignored(self):
        measurement = QueueSpeedMeasurement()
        too_old = time.time() - measurement.MAX_SECONDS_IN_THE_PAST - 1
        measurement._input_timestamps = [too_old, too_old]

        self.assertEqual(measurement.get_input_rpm(), 0.0)

    def test_calculate_rpm_for_single_and_same_time_samples(self):
        measurement = QueueSpeedMeasurement()
        timestamp = time.time()

        self.assertEqual(measurement._calculate_rpm([timestamp]), 0.1)
        self.assertEqual(measurement._calculate_rpm([timestamp, timestamp]), 6000)

    def test_clear(self):
        measurement = QueueSpeedMeasurement()
        measurement._item_added_to_queue()
        measurement._item_left_queue()

        measurement.clear()

        self.assertEqual(measurement.get_input_rpm(), 0.0)
        self.assertEqual(measurement.get_output_rpm(), 0.0)

    def test_many_items(self):
        measurement = QueueSpeedMeasurement()

        for _ in range(measurement.MAX_SIZE * 2):
            measurement._item_added_to_queue()

        self.assertEqual(len(measurement._input_timestamps), measurement.MAX_SIZE - 1)
        self.assertEqual(len(measurement._output_timestamps), 0)
