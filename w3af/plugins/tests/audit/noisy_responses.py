"""
noisy_responses.py

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

import hashlib
import itertools
import threading
import time

from w3af.plugins.tests.audit.vulnerable_responses import html_page


class RequestCounter:
    """
    A thread safe counter, used to give every response a different noise seed.
    """

    def __init__(self):
        self._numbers = itertools.count()
        self._lock = threading.Lock()

    def next(self):
        with self._lock:
            return next(self._numbers)


def noise_lines(seed, count):
    """
    :return: count lines which look random but are fully determined by the seed
    """
    return "<br/>".join(
        hashlib.sha256(f"{seed}-{index}".encode()).hexdigest()[:24]
        for index in range(count)
    )


class RandomLinesPage:
    """
    A page which ignores its parameters and writes a number of lines which
    change in every response, unless static is True.
    """

    def __init__(self, line_count, static=False):
        self.line_count = line_count
        self.static = static
        self._counter = RequestCounter()

    def __call__(self, mock_response, request, uri, response_headers):
        seed = 0 if self.static else self._counter.next()
        return html_page(response_headers, noise_lines(seed, self.line_count))


class RandomDelayPage:
    """
    A page which ignores its parameters and takes a different time to answer
    every time it is requested.
    """

    DELAYS = (0.2, 1.3, 0.6, 1.7)

    def __init__(self):
        self._counter = RequestCounter()

    def __call__(self, mock_response, request, uri, response_headers):
        time.sleep(self.DELAYS[self._counter.next() % len(self.DELAYS)])
        return html_page(response_headers, "Slow page")


class NoisyPage:
    """
    Adds a different noise to every response of another page, as pages that
    show ads or the current time do.
    """

    def __init__(self, page, line_count=3):
        self.page = page
        self.line_count = line_count
        self._counter = RequestCounter()

    def __call__(self, mock_response, request, uri, response_headers):
        status, headers, body = self.page(mock_response, request, uri, response_headers)
        noise = noise_lines(self._counter.next(), self.line_count)
        return status, headers, f"{body}<div>{noise}</div>"
