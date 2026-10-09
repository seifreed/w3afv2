"""
test_aprox_delay_controller.py

Copyright 2012 Andres Riancho

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
from typing import ClassVar

from w3af.core.controllers.delay_detection.aprox_delay import AproxDelay
from w3af.core.controllers.delay_detection.aprox_delay_controller import (
    AproxDelayController,
)
from w3af.core.controllers.delay_detection.tests.scripted_uri_opener import (
    ScriptedUriOpener,
    scripted_wait_times,
)
from w3af.core.data.fuzzer.mutants.querystring_mutant import QSMutant
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.request.fuzzable_request import FuzzableRequest


class TestAproxDelayController(unittest.TestCase):

    TEST_SUITE: ClassVar[list] = [
        # Basic, very easy to pass
        #    The first three 0.1 are for getting the original delay
        #
        #    The first multiplier is triggering a delay
        #
        #    Then we manage the three verification phase loops
        (True, (0.1, 0.1, 0.1, 0.9) * 4),
        # Now the second multiplier is the one which delays
        (
            True,
            (
                0.1,
                0.1,
                0.1,
                0.13,
                0.9,
                0.1,
                0.1,
                0.1,
                0.8,
                0.1,
                0.1,
                0.1,
                0.9,
                0.1,
                0.1,
                0.1,
                1.1,
            ),
        ),
        # Random delays
        (False, (0.1, 1.1, 2.1, 1.9, 1.8, 1.9, 1.7)),
        # Now the third multiplier is the one which delays
        (
            True,
            (
                0.1,
                0.1,
                0.1,
                0.13,
                0.14,
                0.9,
                0.1,
                0.2,
                0.2,
                0.98,
                0.2,
                0.1,
                0.2,
                1.1,
                0.1,
                0.23,
                0.19,
                1.1,
            ),
        ),
        # Unexpected delay
        (False, (0.1, 0.1, 0.1, 2.3, 0.1, 0.1, 0.1, 0.1)),
        (False, (0.1, 0.1, 0.1, 2.3, 0.1, 0.1, 0.1, 0.9, 0.1, 0.1, 0.1, 0.1)),
    ]

    def test_delay_controlled(self):

        for expected_result, delays in self.TEST_SUITE:

            uri_opener = ScriptedUriOpener(
                scripted_wait_times(delays), cache_average_rtt=False
            )
            delay_obj = AproxDelay("%s9!", "1", 10)

            url = URL("http://moth/?id=1")
            req = FuzzableRequest(url)
            mutant = QSMutant(req)
            mutant.set_dc(url.querystring)
            mutant.set_token(("id", 0))

            ed = AproxDelayController(mutant, delay_obj, uri_opener)
            controlled, _responses = ed.delay_is_controlled()
            self.assertEqual(expected_result, controlled, delays)
