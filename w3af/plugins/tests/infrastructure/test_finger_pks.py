"""
test_finger_pks.py

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

from w3af.plugins.infrastructure.finger_pks import finger_pks
from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest

PKS_INDEX = """<html><head><title>Search results for 'bonsai-sec.com'</title></head>
<body><h1>Search results for 'bonsai-sec.com'</h1><pre>Type bits/keyID     Date       User ID
</pre><hr /><pre>
pub  2048R/<a href="/pks/lookup?op=get&amp;search=0x1A2B3C4D">1A2B3C4D</a> 2011-02-01 <a href="/pks/lookup?op=vindex&amp;search=0x1A2B3C4D">Andres Riancho &lt;andres@bonsai-sec.com&gt;</a>
pub  1024D/<a href="/pks/lookup?op=get&amp;search=0x5E6F7A8B">5E6F7A8B</a> 2010-05-12 <a href="/pks/lookup?op=vindex&amp;search=0x5E6F7A8B">Andres Riancho &lt;andres@bonsai-sec.com&gt;</a>
pub  2048R/<a href="/pks/lookup?op=get&amp;search=0x9C0D1E2F">9C0D1E2F</a> 2012-07-30 <a href="/pks/lookup?op=vindex&amp;search=0x9C0D1E2F">Security Team &lt;security@bonsai-sec.com&gt;</a>
pub  2048R/<a href="/pks/lookup?op=get&amp;search=0x3A4B5C6D">3A4B5C6D</a> 2013-01-15 <a href="/pks/lookup?op=vindex&amp;search=0x3A4B5C6D">Other Person &lt;other@example.com&gt;</a>
</pre></body></html>"""


class TestFingerPKS(PluginTest):

    target_url = "http://www.bonsai-sec.com/"

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(
            "http://pgp.mit.edu:11371/pks/lookup?op=index&search=bonsai-sec.com",
            PKS_INDEX,
        ),
    ]

    plugins: ClassVar[dict] = {"infrastructure": (PluginConfig("finger_pks"),)}

    def test_find_pks_email(self):
        self._scan(self.target_url, self.plugins)

        emails = self.kb.get("emails", "emails")

        self.assertEqual(
            {(e["mail"], e["user"], e["name"]) for e in emails},
            {
                ("andres@bonsai-sec.com", "andres", "Andres Riancho"),
                ("security@bonsai-sec.com", "security", "Security Team"),
            },
        )

        for email in emails:
            self.assertEqual(email.get_name(), "Email account")
            self.assertEqual(email.get_url().url_string, "http://pgp.mit.edu:11371/")

    def test_long_description(self):
        self.assertIn("PGP PKS servers", finger_pks().get_long_desc())
