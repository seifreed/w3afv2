"""
dns_cache.py

Copyright 2006 Andres Riancho

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

import socket

from w3af.core.data.misc.lru import SynchronizedLRUDict


class DNSCache:
    """Cache DNS responses without changing process-global socket behavior."""

    CACHE_SIZE = 200

    def __init__(self, output, resolver=socket.getaddrinfo):
        self._output = output
        self._resolver = resolver
        self._cache = SynchronizedLRUDict(self.CACHE_SIZE)

    def getaddrinfo(self, *args, **kwargs):
        query = (args, frozenset(kwargs.items()))

        try:
            return self._cache[query]
        except KeyError:
            result = self._resolver(*args, **kwargs)
            self._cache[query] = result
            self._output.debug(f"DNS response from DNS server for domain: {args[0]}")
            return result

    def clear(self):
        """Release cached DNS responses."""
        self._cache.clear()
