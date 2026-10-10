"""
detect_transparent_proxy.py

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

from w3af.core.controllers.misc.decorators import runonce
from w3af.core.controllers.plugins.infrastructure_plugin import InfrastructurePlugin
from w3af.core.data.kb.info import Info
from w3af.core.exceptions import RunOnce

RANDOM_IPS = (
    "1.2.3.4",
    "5.6.7.8",
    "9.8.7.6",
    "1.2.1.2",
    "1.0.0.1",
    "60.60.60.60",
    "44.44.44.44",
    "11.22.33.44",
    "11.22.33.11",
    "7.99.7.99",
    "87.78.87.78",
)


class detect_transparent_proxy(InfrastructurePlugin):
    """
    Find out if your ISP has a transparent proxy installed.
    :author: Andres Riancho (andres.riancho@gmail.com)
    """

    PROBE_ADDRESSES = tuple((ip_address, 80) for ip_address in RANDOM_IPS)
    CONNECT_TIMEOUT = 5

    def __init__(self, probe_addresses=PROBE_ADDRESSES):
        InfrastructurePlugin.__init__(self)
        self._probe_addresses = probe_addresses

    @runonce(exc_class=RunOnce)
    def discover(self, fuzzable_request, debugging_id):
        """
        :param debugging_id: A unique identifier for this call to discover()
        :param fuzzable_request: A fuzzable_request instance that contains
                                    (among other things) the URL to test.
        """
        if self._is_proxyed_conn():
            desc = (
                "Your ISP seems to have a transparent proxy installed,"
                " this can influence scan results in unexpected ways."
            )

            i = Info("Transparent proxy detected", desc, 1, self.get_name())
            i.set_url(fuzzable_request.get_url())

            self._kb_append(self, "detect_transparent_proxy", i)
            self._output.information(i.get_desc())
        else:
            self._output.information("Your ISP has no transparent proxy.")

    def _is_proxyed_conn(self):
        """
        Connect to "random" addresses, which should not be listening.

        :return: True if all the connections succeed, which means that a
                 proxy is answering them.
        """
        for address in self._probe_addresses:
            try:
                with socket.create_connection(address, timeout=self.CONNECT_TIMEOUT):
                    pass
            except OSError:
                return False

        return True

    def get_long_desc(self):
        """
        :return: A DETAILED description of the plugin functions and features.
        """
        return """
        This plugin tries to detect transparent proxies.

        The procedure for detecting transparent proxies is simple, I try to connect
        to a series of IP addresses, to the port 80, if all of them return an opened
        socket, then it's the proxy server responding.
        """
