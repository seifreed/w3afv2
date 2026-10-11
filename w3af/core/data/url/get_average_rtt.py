"""
get_average_rtt.py

Copyright 2018 Andres Riancho

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
import logging
import threading
import time

from w3af.core.data.constants.encodings import DEFAULT_ENCODING
from w3af.core.data.misc.encoding import smart_unicode
from w3af.core.data.misc.lru import SynchronizedLRUDict

LOGGER = logging.getLogger(__name__)


class GetAverageRTTForMutant:

    def __init__(self, url_opener, timeout=120, cache_ttl=5):
        """
        :param url_opener: Sends the HTTP requests used to measure the RTT
        :param timeout: Seconds to wait for another thread measuring the same
                        mutant before measuring it ourselves
        :param cache_ttl: Seconds during which a measured RTT is reused
        """
        self._url_opener = url_opener
        self._timeout = timeout
        self._cache_ttl = cache_ttl

        # Cache to measure RTT
        self._rtt_mutant_cache = SynchronizedLRUDict(capacity=128)
        self._rtt_processing_events = {}

    def _get_cache_key(self, mutant):
        #
        # Get the cache key for this mutant
        #
        method = mutant.get_method()
        uri = mutant.get_uri()
        data = mutant.get_data()
        headers = mutant.get_all_headers()

        cache_key_parts = [method, uri, data, headers]
        digest = hashlib.sha256()
        for part in cache_key_parts:
            digest.update(smart_unicode(part, errors="ignore").encode(DEFAULT_ENCODING))
            digest.update(b"\0")

        return digest.hexdigest()

    def get_average_rtt_for_mutant(self, mutant, count=3, debugging_id=None):
        """
        Get the average time for the HTTP request represented as a mutant.

        This method caches responses. The cache entries are valid for 5 seconds,
        after that period of time the entry is removed from the cache, the average RTT
        is re-calculated and stored again.

        :param mutant: The mutant to send and measure RTT from
        :param count: Number of checks to perform
        :param debugging_id: Unique ID used for logging
        :return: A float representing the seconds it took to get the response
        """
        if count < 3:
            raise ValueError("Count must be greater or equal than 3.")

        #
        # First we try to get the data from the cache
        #
        cache_key = self._get_cache_key(mutant)
        cached_rtt = self._get_cached_rtt(cache_key, debugging_id=debugging_id)

        if cached_rtt is not None:
            return cached_rtt

        #
        # Only perform one of these checks at the time, this is useful to prevent
        # different threads which need the same result from duplicating efforts
        #
        rtt_processing_event = self._rtt_processing_events.get(cache_key, None)

        if rtt_processing_event is not None:
            # There is another thread sending HTTP requests to get the average RTT
            # we need to wait for that thread to finish
            wait_result = rtt_processing_event.wait(timeout=self._timeout)

            if not wait_result:
                # The TIMEOUT has been reached, the thread that was trying to get
                # the RTT for us found a serious issue, is dead-locked, etc.
                #
                # We're going to have to try to get the RTT ourselves by sending
                # the HTTP requests. Just `pass` here and get to the code below
                # that sends the HTTP requests
                msg = (
                    "get_average_rtt_for_mutant() timed out waiting for"
                    " results from another thread. Will send HTTP requests"
                    " and collect the data from the network (did:%s)"
                )
                log_args = (debugging_id,)
                LOGGER.debug(msg, *log_args)
            else:
                # The event was set! The other thread finished and we can read
                # the result from the cache.
                #
                # Just in case the other thread had issues getting the RTTs, we
                # need to check if the cache actually has the data, and if the
                # data is valid
                #
                # No need to check the timestamp because we know it will be
                # valid, it has been just set by the other thread
                cached_rtt = self._get_cached_rtt(cache_key, debugging_id=debugging_id)

                if cached_rtt is not None:
                    return cached_rtt

                msg = (
                    "get_average_rtt_for_mutant() found no cache entry after"
                    " the other thread finished. Will send HTTP requests"
                    " and collect the data from the network (did:%s)"
                )
                timeout_log_args = (debugging_id,)
                LOGGER.debug(msg, *timeout_log_args)

        #
        # There is no other thread getting data for `cache_key`, we'll have to
        # extract the information by sending the HTTP requests
        #
        event = threading.Event()
        self._rtt_processing_events[cache_key] = event

        try:
            rtts = self._get_all_rtts(mutant, count, debugging_id)
            average_rtt = float(sum(rtts)) / len(rtts)
            self._rtt_mutant_cache[cache_key] = (time.time(), average_rtt)
        finally:
            event.set()
            self._rtt_processing_events.pop(cache_key, None)

        msg = "Returning fresh average RTT of %.2f seconds for mutant %s (did:%s)"
        result_log_args = (average_rtt, cache_key, debugging_id)
        LOGGER.debug(msg, *result_log_args)

        return average_rtt

    def _get_cached_rtt(self, cache_key, debugging_id):
        cached_value = self._rtt_mutant_cache.get(cache_key, default=None)

        if cached_value is None:
            return None

        timestamp, value = cached_value
        if time.time() - timestamp > self._cache_ttl:
            return None

        # The cache entry is still valid, return the cached value
        msg = "Returning cached average RTT of %.2f seconds for mutant %s (did:%s)"
        args = (value, cache_key, debugging_id)
        LOGGER.debug(msg, *args)
        return value

    def _get_all_rtts(self, mutant, count=3, debugging_id=None):
        """
        :param mutant: The mutant to send and measure RTT from
        :param count: Number of checks to perform
        :param debugging_id: Unique ID used for logging
        :return: A float representing the seconds it took to get the response
        """
        rtts = []

        for _ in range(count):
            resp = self._url_opener.send_mutant(
                mutant, cache=False, grep=False, debugging_id=debugging_id
            )
            rtt = resp.get_wait_time()
            rtts.append(rtt)

        return rtts
