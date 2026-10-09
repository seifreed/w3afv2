"""
test_dns_cache.py

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

import socket
import unittest

from w3af.core.controllers.misc import dns_cache
from w3af.core.controllers.misc.dns_cache import enable_dns_cache


class TestDNSCache(unittest.TestCase):
    def test_enable_replaces_getaddrinfo(self):
        enable_dns_cache()
        enable_dns_cache()

        self.assertIs(socket.getaddrinfo, dns_cache._caching_getaddrinfo)

    def test_second_query_is_served_from_cache(self):
        enable_dns_cache()

        first = socket.getaddrinfo("localhost", 80)
        second = socket.getaddrinfo("localhost", 80)

        self.assertIs(first, second)
        self.assertIn(
            (("localhost", 80), frozenset()), list(dns_cache._dns_cache.keys())
        )

    def test_keyword_arguments_are_part_of_the_key(self):
        enable_dns_cache()

        tcp = socket.getaddrinfo("localhost", 80, type=socket.SOCK_STREAM)
        udp = socket.getaddrinfo("localhost", 80, type=socket.SOCK_DGRAM)

        self.assertTrue(all(info[1] == socket.SOCK_STREAM for info in tcp))
        self.assertTrue(all(info[1] == socket.SOCK_DGRAM for info in udp))
