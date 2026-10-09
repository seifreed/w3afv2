"""
test_xssed_dot_com.py

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
from w3af.core.data.parsers.doc.url import URL
from w3af.plugins.infrastructure.xssed_dot_com import xssed_dot_com
from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest

SEARCH_RESULTS = """<html><body><table>
<tr><th class="row3">Date</th><th class="row3">Author</th></tr>
<tr><td>
<a href='/mirror/76754/' target='_blank'>alarabiya.net</a>
</td></tr>
<tr><td>
<a href='/mirror/12345/' target='_blank'>www.alarabiya.net</a>
</td></tr>
</table></body></html>"""

NO_SEARCH_RESULTS = """<html><body>
<p>No results were found for your search.</p>
</body></html>"""

UNFIXED_MIRROR = """<html><body><table>
<tr><th class="row3">Status: UNFIXED</th></tr>
<tr><th class="row3">URL: http://www.alarabiya.net/search.php?q=%3Cscript%3Ealert(1)<br>%3C/script%3E</th></tr>
</table></body></html>"""

FIXED_MIRROR = """<html><body><table>
<tr><th class="row3">Status: FIXED</th></tr>
<tr><th class="row3">URL: http://www.alarabiya.net/index.php?id=&quot;&gt;xss</th></tr>
</table></body></html>"""


class TestXssedDotCom(PluginTest):

    target_url = "http://www.alarabiya.net/"

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse("http://www.xssed.com/search?key=.alarabiya.net", SEARCH_RESULTS),
        MockResponse("http://www.xssed.com/search?key=.digi.ninja", NO_SEARCH_RESULTS),
        MockResponse("http://www.xssed.com/mirror/76754/", UNFIXED_MIRROR),
        MockResponse("http://www.xssed.com/mirror/12345/", FIXED_MIRROR),
    ]

    plugins: ClassVar[dict] = {"infrastructure": (PluginConfig("xssed_dot_com"),)}

    def test_xssed_dot_com_positive(self):
        self._scan(self.target_url, self.plugins)

        vulns = self.kb.get("xssed_dot_com", "xss")
        self.assertEqual(len(vulns), 2, vulns)

        by_severity = {vuln.get_severity(): vuln for vuln in vulns}

        unfixed = by_severity[severity.HIGH]
        self.assertEqual(unfixed.get_name(), "Potential XSS vulnerability")
        self.assertIn("the target domain contains a XSS", unfixed.get_desc())
        self.assertIn("http://www.xssed.com/mirror/76754/", unfixed.get_desc())
        self.assertEqual(
            unfixed.get_uri(),
            URL("http://www.alarabiya.net/search.php?q=<script>alert(1)</script>"),
        )

        fixed = by_severity[severity.LOW]
        self.assertIn("the target domain contained a XSS", fixed.get_desc())
        self.assertEqual(
            fixed.get_uri(),
            URL('http://www.alarabiya.net/index.php?id=">xss'),
        )

    def test_xssed_dot_com_negative(self):
        """
        Searching ".digi.ninja" instead of "digi.ninja" prevents the too
        generic matches reported in issue #12717.
        """
        self._scan("https://digi.ninja/", self.plugins)

        self.assertEqual(self.kb.get("xssed_dot_com", "xss"), [])

    def test_long_description(self):
        self.assertIn("xssed.com", xssed_dot_com().get_long_desc())
