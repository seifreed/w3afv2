"""
smart_queue.py

Copyright 2013 Andres Riancho

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


class QueueSpeedMeasurement:

    MAX_SIZE = 20000
    MAX_SECONDS_IN_THE_PAST = 600

    def __init__(self):
        self._output_timestamps = []
        self._input_timestamps = []

    def clear(self):
        self._output_timestamps = []
        self._input_timestamps = []

    def get_input_rpm(self):
        return self._calculate_rpm(self._input_timestamps)

    def get_output_rpm(self):
        return self._calculate_rpm(self._output_timestamps)

    def _item_left_queue(self):
        self._add(self._output_timestamps)

    def _item_added_to_queue(self):
        self._add(self._input_timestamps)

    def _add(self, data):
        data.append(time.time())

        while len(data) >= self.MAX_SIZE:
            data.pop(0)

    def _calculate_rpm(self, data):
        # We're only going to analyze the last MAX_SECONDS_IN_THE_PAST seconds
        max_past_time = time.time() - self.MAX_SECONDS_IN_THE_PAST
        data = [ts for ts in data if ts > max_past_time]

        if len(data) == 0:
            # The last MAX_SECONDS_IN_THE_PAST seconds had no activity,
            # the RPM is zero!
            return 0.0

        if len(data) == 1:
            # The last MAX_SECONDS_IN_THE_PAST seconds only had one
            # read / write action
            return 60.0 / self.MAX_SECONDS_IN_THE_PAST

        #
        # We have at least two read / write actions in the last
        # MAX_SECONDS_IN_THE_PAST seconds calculate the RPM!
        #
        first_item = data[0]

        # Get the last logged item time
        last_item = data[-1]

        # Count all items that were logged in the last MAX_SECONDS_IN_THE_PAST
        all_intervals = len(data) - 1

        time_delta = last_item - first_item

        # Protect against cases in which the two items were added "at the same
        # time" such as https://github.com/andresriancho/w3af/issues/342
        if time_delta == 0:
            time_delta = 0.01

        # Calculate RPM and return it
        return 60.0 * all_intervals / time_delta
