"""
test_find_jboss.py

Copyright 2012 Andres Riancho

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

from typing import ClassVar

from w3af.core.data.constants import severity
from w3af.plugins.infrastructure.find_jboss import find_jboss
from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest

TARGET = "http://jboss/"

JMX_INVOKER_RESPONSE = (
    b"\xac\xed\x00\x05sr\x00$org.jboss.invocation.MarshalledValue"
    b"\xeb\xcc\xe0\xd1\xf4J\xd0\x99\x0c\x00\x00xpz\x00\x00\x04\x00"
)

STATUS_PAGE = (
    "<html><head><title>Tomcat Status</title></head><body>"
    "<h1>Server Status</h1><p>JVM free memory: 1024 MB</p></body></html>"
)


class TestFindJBoss(PluginTest):

    target_url = TARGET

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(TARGET, "<html><body>Welcome to JBoss AS</body></html>"),
        MockResponse(
            TARGET + "invoker/JMXInvokerServlet",
            JMX_INVOKER_RESPONSE,
            content_type="application/x-java-serialized-object",
        ),
        MockResponse(TARGET + "status", STATUS_PAGE),
    ]

    plugins: ClassVar[dict] = {"infrastructure": (PluginConfig("find_jboss"),)}

    def test_find_jboss(self):
        self._scan(self.target_url, self.plugins)

        findings = {i.get_name(): i for i in self.kb.get("find_jboss", "find_jboss")}

        self.assertEqual(
            set(findings),
            {"JMX Invoker enabled without Auth", "JBoss Status Servlet found"},
        )

        invoker = findings["JMX Invoker enabled without Auth"]
        self.assertEqual(invoker.get_severity(), severity.LOW)
        self.assertEqual(
            invoker.get_url().url_string, TARGET + "invoker/JMXInvokerServlet"
        )

        status = findings["JBoss Status Servlet found"]
        self.assertEqual(status.get_severity(), severity.INFORMATION)

    def test_long_description(self):
        self.assertIn("JBoss", find_jboss().get_long_desc())
