"""
scripted_uri_opener.py

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

import random

from w3af.core.data.dc.headers import Headers
from w3af.core.data.url.get_average_rtt import GetAverageRTTForMutant
from w3af.core.data.url.http_response import HTTPResponse


def scripted_wait_times(wanted_delays, rand_range=(0, 0)):
    for delay_secs in wanted_delays:
        yield delay_secs + random.randint(*rand_range) / 10.0


class ScriptedUriOpener:
    """
    URI opener for the delay controllers which, instead of measuring the
    network, answers every sent mutant with an HTTP response whose wait time
    is the next one in a pre-recorded sequence.

    :param wait_times: Iterable with the wait time of each response
    :param cache_average_rtt: When True the average RTT is cached the same way
                              ExtendedUrllib does, otherwise a fresh average
                              is measured on each call.
    """

    def __init__(self, wait_times, cache_average_rtt):
        self._wait_times = iter(wait_times)
        self._cache_average_rtt = cache_average_rtt
        self._average_rtt = GetAverageRTTForMutant(self)

    def send_mutant(self, mutant, **_kwargs):
        url = mutant.get_uri()
        response = HTTPResponse(200, "", Headers(), url, url)
        response.set_wait_time(next(self._wait_times))
        return response

    def get_average_rtt_for_mutant(self, mutant, debugging_id=None):
        average_rtt = self._average_rtt
        if not self._cache_average_rtt:
            average_rtt = GetAverageRTTForMutant(self)

        return average_rtt.get_average_rtt_for_mutant(mutant, debugging_id=debugging_id)
