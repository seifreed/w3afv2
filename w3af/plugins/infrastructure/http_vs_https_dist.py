"""
http_vs_https_dist.py

Copyright 2011 Andres Riancho

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

from scapy.error import Scapy_Exception

from w3af.core.controllers.misc.decorators import runonce
from w3af.core.controllers.plugins.infrastructure_plugin import InfrastructurePlugin
from w3af.core.data.kb.info import Info
from w3af.core.data.options.opt_factory import opt_factory
from w3af.core.data.options.option_list import OptionList
from w3af.core.data.options.option_types import INT
from w3af.core.exceptions import RunOnce

TRACEROUTE_ERROR_MSG = (
    "w3af won't be able to run plugin infrastructure.http_vs_https_dist."
    ' Scapy\'s traceroute failed with: "%s". Note that tracing routes'
    " requires enough privileges to send and capture raw packets."
)


class http_vs_https_dist(InfrastructurePlugin):
    """
    Determines the network distance between the http and https ports for a target

    :author: Javier Andalia <jandalia =at= gmail.com>
    """

    def __init__(self):
        InfrastructurePlugin.__init__(self)

        self._http_port = 80
        self._https_port = 443

    @runonce(exc_class=RunOnce)
    def discover(self, fuzzable_request, debugging_id):
        """
        Discovery task. Uses scapy.traceroute function in order to determine
        the distance between http and https ports for the target.
        Intended to be executed once during the infrastructure process.

        :param debugging_id: A unique identifier for this call to discover()
        :param fuzzable_request: A fuzzable_request instance that contains
                                    (among other things) the URL to test.
        """
        target_url = fuzzable_request.get_url()
        domain = target_url.get_domain()
        http_port, https_port = self.get_target_ports(target_url)

        try:
            https_troute = _traceroute(domain, https_port)
            http_troute = _traceroute(domain, http_port)
        except (OSError, Scapy_Exception) as e:
            # Raised when the user has no privileges to send raw packets, and
            # also when the domain can not be resolved or resolves to an IPv6
            # address, which scapy's traceroute does not support.
            self._output.error(TRACEROUTE_ERROR_MSG % e)
            return

        self.report_routes(domain, http_port, https_port, http_troute, https_troute)

    def get_target_ports(self, target_url):
        """
        :return: The (http_port, https_port) tuple to trace, using the port
                 from the target URL for its own protocol when present
        """
        http_port = self._http_port
        https_port = self._https_port

        netloc = target_url.get_net_location()
        try:
            port = int(netloc.split(":")[-1])
        except ValueError:
            return http_port, https_port

        if target_url.get_protocol() == "https":
            return http_port, port

        return port, https_port

    def report_routes(self, domain, http_port, https_port, http_troute, https_troute):
        """
        Compare the traceroute results for the HTTP and HTTPS ports and report
        the differences.

        :param http_troute: The scapy trace dict for the HTTP port, which looks
                            like {destination: {ttl: (ip_address, reached)}}
        :param https_troute: The scapy trace dict for the HTTPS port
        """
        # This destination was probably 'localhost' or a host reached
        # through a vpn?
        if not (https_troute and http_troute):
            return

        https_ip_tuples = list(next(iter(https_troute.values())).values())
        last_https_ip = https_ip_tuples[-1]
        http_ip_tuples = list(next(iter(http_troute.values())).values())
        last_http_ip = http_ip_tuples[-1]

        # Last IP should be True; otherwise the dest wasn't reached
        # Tuples have the next form: ('192.168.1.1', False)
        if not (last_https_ip[1] and last_http_ip[1]):
            desc = "The port '%s' is not open on target %s"
            if not last_https_ip[1]:
                self._output.error(desc % (https_port, domain))
            if not last_http_ip[1]:
                self._output.error(desc % (http_port, domain))
            return

        if http_ip_tuples != https_ip_tuples:
            header = "  TCP trace to %s:%s\n%s"

            trc1 = header % (domain, http_port, _trace_str(http_ip_tuples))
            trc2 = header % (domain, https_port, _trace_str(https_ip_tuples))

            desc = (
                'Routes to target "%s" using ports %s and ' "%s are different:\n%s\n%s"
            )
            desc %= (domain, http_port, https_port, trc1, trc2)
            self._report_info("HTTP and HTTPs hop distance", desc)
            self._output.information(desc)
        else:
            desc = (
                "The routes to the target's HTTP and HTTPS ports are"
                f" the same:\n{_trace_str(http_ip_tuples)}"
            )
            self._report_info("HTTP traceroute", desc)

    def _report_info(self, name, desc):
        i = Info(name, desc, 1, self.get_name())
        self._kb_append(self, "http_vs_https_dist", i)

    def get_options(self):
        """
        :return: A list of option objects for this plugin.
        """
        ol = OptionList()
        d1 = "Destination http port number to analize"
        o1 = opt_factory("httpPort", self._http_port, d1, INT, help=d1)
        ol.add(o1)

        d2 = "Destination httpS port number to analize"
        o2 = opt_factory("httpsPort", self._https_port, d2, INT, help=d2)
        ol.add(o2)

        return ol

    def set_options(self, options):
        """
        Sets all the options that are configured using the UI generated by
        the framework using the result of get_options().

        :param options: A dictionary with the options for the plugin.
        """
        self._http_port = options["httpPort"].get_value()
        self._https_port = options["httpsPort"].get_value()

    def get_long_desc(self):
        """
        :return: A DETAILED description of the plugin functions and features.
        """
        return """
        This plugin analyzes the network distance between the HTTP and HTTPS ports
        giving a detailed report of the traversed hosts in transit to <target:port>.
        You should have root/admin privileges in order to run this plugin succesfully.

        Explicitly declared ports on the entered target override those specified
        in the config fields.
        For example, if the user sets 'https://host.tld:444' as target and the httpPort
        value is 443; then '444' will be used.

        HTTP and HTTPS ports default to 80 and 443.
        """


def _trace_str(ip_tuples):
    return "\n".join(
        f"    {hop} {ip_tuple[0]}" for hop, ip_tuple in enumerate(ip_tuples)
    )


def _traceroute(domain, port):
    """
    Import scapy.all only when tracing, the import uses a lot of memory.

    :return: The scapy trace dict for a TCP traceroute to domain:port
    """
    from scapy.all import traceroute

    return traceroute(domain, dport=port, verbose=0)[0].get_trace()
