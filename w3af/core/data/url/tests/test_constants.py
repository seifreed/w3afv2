"""
test_constants.py

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

import unittest

from w3af.core.data.url.constants import MAX_ERROR_COUNT, MAX_RESPONSE_COLLECT


class TestURLConstants(unittest.TestCase):
    def test_error_rate_window_holds_twice_the_error_count(self):
        """
        xurllib computes the error rate over the last MAX_RESPONSE_COLLECT
        responses and stops the scan after MAX_ERROR_COUNT errors, so the
        window must be large enough to hold them.
        """
        self.assertGreater(MAX_RESPONSE_COLLECT, MAX_ERROR_COUNT * 2)
