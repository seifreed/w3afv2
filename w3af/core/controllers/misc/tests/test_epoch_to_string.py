"""
test_epoch_to_string.py

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

import time
import unittest

from w3af.core.controllers.misc.epoch_to_string import epoch_to_string

MINUTE = 60
HOUR = 60 * MINUTE
DAY = 24 * HOUR
WEEK = 7 * DAY


def seconds_ago(seconds):
    # Half a second of slack keeps the integer seconds stable while the
    # assertion runs
    return time.time() - seconds - 0.5


class TestEpochToString(unittest.TestCase):
    def test_now(self):
        self.assertEqual(epoch_to_string(time.time()), "0 seconds")

    def test_singular_units(self):
        elapsed = WEEK + DAY + HOUR + MINUTE + 1

        self.assertEqual(
            epoch_to_string(seconds_ago(elapsed)),
            "1 week 1 day 1 hour 1 minute 1 second",
        )

    def test_plural_units(self):
        elapsed = 2 * WEEK + 3 * DAY + 4 * HOUR + 5 * MINUTE + 6

        self.assertEqual(
            epoch_to_string(seconds_ago(elapsed)),
            "2 weeks 3 days 4 hours 5 minutes 6 seconds",
        )

    def test_only_minutes(self):
        self.assertEqual(epoch_to_string(seconds_ago(MINUTE)), "1 minute")
