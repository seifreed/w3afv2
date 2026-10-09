"""
get_net_iface.py

Copyright 2009 Andres Riancho

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

import psutil

from w3af.core.controllers.misc.get_local_ip import get_local_ip

DEFAULT_INTERFACE = "eth0"


def get_net_iface():
    """
    :return: The interface name that is being used to connect to the net.
    """
    return interface_for_ip(get_local_ip())


def interface_for_ip(ip_address):
    """
    :param ip_address: An IPv4 address assigned to this host
    :return: The name of the interface which holds ip_address, or
             DEFAULT_INTERFACE when no interface has it.
    """
    for name, addresses in psutil.net_if_addrs().items():
        for address in addresses:
            if address.family == socket.AF_INET and address.address == ip_address:
                return name

    return DEFAULT_INTERFACE
