"""
test_network_helpers.py

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

import psutil

from w3af.core.controllers.misc.get_local_ip import get_local_ip
from w3af.core.controllers.misc.get_net_iface import (
    DEFAULT_INTERFACE,
    get_net_iface,
    interface_for_ip,
)
from w3af.core.controllers.misc.get_unused_port import get_unused_port


def interfaces_with_ip(ip_address):
    return [
        name
        for name, addresses in psutil.net_if_addrs().items()
        if any(address.address == ip_address for address in addresses)
    ]


class TestGetLocalIP(unittest.TestCase):
    def test_loopback_target(self):
        self.assertEqual(get_local_ip("127.0.0.1"), "127.0.0.1")

    def test_default_target_returns_an_ipv4_address_or_none(self):
        local_ip = get_local_ip()

        if local_ip is not None:
            socket.inet_aton(local_ip)

    def test_unresolvable_target(self):
        self.assertIsNone(get_local_ip("256.256.256.256"))


class TestGetNetIface(unittest.TestCase):
    def test_loopback_interface(self):
        self.assertIn(interface_for_ip("127.0.0.1"), interfaces_with_ip("127.0.0.1"))

    def test_unknown_address_uses_default(self):
        self.assertEqual(interface_for_ip("192.0.2.123"), DEFAULT_INTERFACE)

    def test_interface_used_to_reach_the_internet(self):
        local_ip = get_local_ip()
        expected = interfaces_with_ip(local_ip) or [DEFAULT_INTERFACE]

        self.assertIn(get_net_iface(), expected)


class TestGetUnusedPort(unittest.TestCase):
    def test_port_can_be_bound(self):
        port = get_unused_port()

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", port))
            self.assertEqual(sock.getsockname()[1], port)
