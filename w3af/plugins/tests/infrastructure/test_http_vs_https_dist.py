"""
test_http_vs_https_dist.py

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

import copy
import unittest
from typing import ClassVar

import pytest
from scapy.error import Scapy_Exception

import w3af.core.data.kb.knowledge_base as kb
import w3af.plugins.infrastructure.http_vs_https_dist as hvshsdist
from w3af.core.controllers.exceptions import RunOnce
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.request.fuzzable_request import FuzzableRequest
from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest
from w3af.plugins.tests.text_file_log import TextFileLog

DIFFERENT_ROUTES_DESC = (
    'Routes to target "host.tld" using ports 80 and %s are different:\n'
    "  TCP trace to host.tld:80\n"
    "    0 192.168.1.1\n    1 200.200.0.0\n    2 207.46.47.14\n"
    "  TCP trace to host.tld:%s\n"
    "    0 192.168.1.1\n    1 200.115.195.33\n    2 207.46.47.14"
)


def can_run_traceroute():
    try:
        hvshsdist._traceroute("127.0.0.1", 80)
    except (OSError, Scapy_Exception):
        return False
    return True


class test_http_vs_https_dist(unittest.TestCase):
    """
    :author: Javier Andalia <jandalia =at= gmail.com>
    """

    tracedict: ClassVar[dict] = {
        "localhost": {
            1: ("192.168.1.1", False),
            3: ("200.115.195.33", False),
            5: ("207.46.47.14", True),
        }
    }

    def setUp(self):
        kb.kb.cleanup()
        self.plugininst = hvshsdist.http_vs_https_dist()
        self.plugininst.set_knowledge_base(kb.kb)

    def _different_route_traces(self):
        """
        :return: (http_trace, https_trace) with one different hop
        """
        http_trace = copy.deepcopy(self.tracedict)
        http_trace["localhost"][3] = ("200.200.0.0", False)
        return http_trace, copy.deepcopy(self.tracedict)

    def _reported_infos(self):
        return kb.kb.get("http_vs_https_dist", "http_vs_https_dist")

    def _attach_log(self):
        log = TextFileLog()
        self.addCleanup(log.remove)
        return log

    def test_target_ports_override_https_port(self):
        ports = self.plugininst.get_target_ports(URL("https://host.tld:4444/"))
        self.assertEqual(ports, (80, 4444))

    def test_target_ports_override_http_port(self):
        ports = self.plugininst.get_target_ports(URL("http://host.tld:8080/"))
        self.assertEqual(ports, (8080, 443))

    def test_target_ports_default(self):
        ports = self.plugininst.get_target_ports(URL("https://host.tld/"))
        self.assertEqual(ports, (80, 443))

    def test_report_override_port(self):
        http_trace, https_trace = self._different_route_traces()
        log = self._attach_log()

        with log.attached_to_output_manager():
            self.plugininst.report_routes("host.tld", 80, 4444, http_trace, https_trace)

        result = DIFFERENT_ROUTES_DESC % (4444, 4444)
        infos = self._reported_infos()
        self.assertEqual(len(infos), 1)
        self.assertEqual(infos[0].get_name(), "HTTP and HTTPs hop distance")
        self.assertEqual(infos[0].get_desc(with_id=False), result)
        self.assertTrue(log.contains("information", result))

    def test_report_eq_routes(self):
        http_trace = copy.deepcopy(self.tracedict)
        https_trace = copy.deepcopy(self.tracedict)
        log = self._attach_log()

        with log.attached_to_output_manager():
            self.plugininst.report_routes("host.tld", 80, 80, http_trace, https_trace)

        infos = self._reported_infos()
        self.assertEqual(len(infos), 1)

        info = infos[0]
        self.assertEqual("HTTP traceroute", info.get_name())
        self.assertTrue("are the same" in info.get_desc())
        self.assertFalse(log.contains("information", info.get_desc(with_id=False)))

    def test_report_diff_routes(self):
        http_trace, https_trace = self._different_route_traces()
        log = self._attach_log()

        with log.attached_to_output_manager():
            self.plugininst.report_routes("host.tld", 80, 443, http_trace, https_trace)

        result = DIFFERENT_ROUTES_DESC % (443, 443)
        infos = self._reported_infos()
        self.assertEqual(len(infos), 1)
        self.assertEqual(infos[0].get_desc(with_id=False), result)
        self.assertTrue(log.contains("information", result))

    def test_report_unreachable_port(self):
        http_trace = copy.deepcopy(self.tracedict)
        http_trace["localhost"][5] = ("207.46.47.14", False)
        log = self._attach_log()

        with log.attached_to_output_manager():
            self.plugininst.report_routes(
                "host.tld", 80, 443, http_trace, copy.deepcopy(self.tracedict)
            )

        self.assertEqual(self._reported_infos(), [])
        self.assertTrue(
            log.contains("error", "The port '80' is not open on target host.tld")
        )

    def test_report_both_ports_unreachable(self):
        http_trace = copy.deepcopy(self.tracedict)
        http_trace["localhost"][5] = ("207.46.47.14", False)
        https_trace = copy.deepcopy(http_trace)
        log = self._attach_log()

        with log.attached_to_output_manager():
            self.plugininst.report_routes("host.tld", 80, 443, http_trace, https_trace)

        self.assertEqual(self._reported_infos(), [])
        self.assertTrue(
            log.contains("error", "The port '443' is not open on target host.tld")
        )
        self.assertTrue(
            log.contains("error", "The port '80' is not open on target host.tld")
        )

    def test_report_without_traces(self):
        self.plugininst.report_routes("localhost", 80, 443, {}, {})

        self.assertEqual(self._reported_infos(), [])

    def test_discover_runonce(self):
        """Discovery routine must be executed only once. Upcoming calls should
        fail"""
        fuzz_req = FuzzableRequest(URL("https://unresolvable.invalid/"))

        self.plugininst.discover(fuzz_req, None)
        self.assertRaises(RunOnce, self.plugininst.discover, fuzz_req, None)

    def test_traceroute_failure_is_reported(self):
        log = self._attach_log()
        fuzz_req = FuzzableRequest(URL("https://unresolvable.invalid/"))

        with log.attached_to_output_manager():
            self.plugininst.discover(fuzz_req, None)

        with self.assertRaises((OSError, Scapy_Exception)) as traceroute_error:
            hvshsdist._traceroute("unresolvable.invalid", 443)

        expected = hvshsdist.TRACEROUTE_ERROR_MSG % traceroute_error.exception
        self.assertEqual(self._reported_infos(), [])
        self.assertTrue(log.contains("error", expected))

    def test_options_round_trip(self):
        options = self.plugininst.get_options()
        options["httpPort"].set_value(8080)
        options["httpsPort"].set_value(8443)

        self.plugininst.set_options(options)

        ports = self.plugininst.get_target_ports(URL("http://host.tld/"))
        self.assertEqual(ports, (8080, 8443))

    def test_long_desc_mentions_privileges(self):
        self.assertIn("privileges", self.plugininst.get_long_desc())


@pytest.mark.skipif(
    not can_run_traceroute(), reason="this user can not send raw packets"
)
class TestHTTPvsHTTPS(PluginTest):
    """
    Trace the routes to the loopback interface, where both the HTTP and HTTPS
    ports answer with a TCP reset, while the canned server answers the HTTP
    requests sent to the target.
    """

    target_url = "http://127.0.0.1/"

    MOCK_RESPONSES: ClassVar[list] = [MockResponse(target_url, "Hello world")]

    def test_trace(self):
        plugins = {"infrastructure": (PluginConfig("http_vs_https_dist"),)}
        self._scan(self.target_url, plugins)

        infos = self.kb.get("http_vs_https_dist", "http_vs_https_dist")

        self.assertEqual(len(infos), 1, infos)

        info = infos[0]
        self.assertEqual("HTTP traceroute", info.get_name())
