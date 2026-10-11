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

import w3af.core.controllers.output_manager as om
from w3af.core.controllers.misc.dns_cache import DNSCache


class TestDNSCache(unittest.TestCase):
    def setUp(self):
        self.cache = DNSCache(om.out)
        self.addCleanup(self.cache.clear)

    def test_cache_does_not_replace_process_resolver(self):
        original = socket.getaddrinfo

        self.cache.getaddrinfo("localhost", 80)

        self.assertIs(socket.getaddrinfo, original)

    def test_second_query_is_served_from_cache(self):
        first = self.cache.getaddrinfo("localhost", 80)
        second = self.cache.getaddrinfo("localhost", 80)

        self.assertIs(first, second)
        self.assertEqual(len(self.cache._cache), 1)

    def test_keyword_arguments_are_part_of_the_key(self):
        tcp = self.cache.getaddrinfo("localhost", 80, type=socket.SOCK_STREAM)
        udp = self.cache.getaddrinfo("localhost", 80, type=socket.SOCK_DGRAM)

        self.assertTrue(all(info[1] == socket.SOCK_STREAM for info in tcp))
        self.assertTrue(all(info[1] == socket.SOCK_DGRAM for info in udp))

    def test_clear_releases_cached_responses(self):
        self.cache.getaddrinfo("localhost", 80)

        self.cache.clear()

        self.assertEqual(len(self.cache._cache), 0)
