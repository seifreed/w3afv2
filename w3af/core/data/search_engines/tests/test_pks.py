"""
test_pks.py

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

import unittest

from w3af.core.data.search_engines.pks import PKSResult, pks
from w3af.core.data.search_engines.tests.fixture_proxy import (
    DROP_CONNECTION,
    FixtureProxy,
)
from w3af.core.exceptions import BaseFrameworkException

#
# Based on the output of:
# wget 'http://pgp.mit.edu:11371/pks/lookup?op=index&search=bonsai-sec.com'
#
BODY = """\
<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd" >
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
<title>Search results for 'sec com bonsai'</title>
<meta http-equiv="Content-Type" content="text/html;charset=utf-8" />
</head><body><h1>Search results for 'sec com bonsai'</h1><pre>Type bits/keyID     Date       User ID
</pre><hr /><pre>
pub  2048R/<a href="/pks/lookup?op=get&amp;search=0x8C9D86461E9B9265">1E9B9265</a> 2010-05-06 <a href="/pks/lookup?op=vindex&amp;search=0x8C9D86461E9B9265">Lucas Apa (Bonsai Security Consultant) &lt;lucas@bonsai-sec.com&gt;</a>
</pre><hr /><pre>
pub  1024D/<a href="/pks/lookup?op=get&amp;search=0x3608ED24EB0B8821">EB0B8821</a> 2010-04-11 <a href="/pks/lookup?op=vindex&amp;search=0x3608ED24EB0B8821">Nahuel Grisolia &lt;nahuel@bonsai-sec.com&gt;</a>
</pre><hr /><pre>
pub  1024D/<a href="/pks/lookup?op=get&amp;search=0x0000000000000001">00000001</a> 2011-01-01 <a href="/pks/lookup?op=vindex&amp;search=0x0000000000000001">Nahuel Again &lt;nahuel@bonsai-sec.com&gt;</a>
</pre><hr /><pre>
pub  1024D/<a href="/pks/lookup?op=get&amp;search=0x0000000000000002">00000002</a> 2011-01-01 <a href="/pks/lookup?op=vindex&amp;search=0x0000000000000002">Someone Else &lt;someone@other.com&gt;</a>
</pre><hr /><pre>
pub  1024D/<a href="/pks/lookup?op=get&amp;search=0x0000000000000003">00000003</a> 2011-01-01 <a href="/pks/lookup?op=vindex&amp;search=0x0000000000000003">No Email Here</a>
</pre><pre>
short line
</pre></body></html>
"""


class TestPKS(unittest.TestCase):

    def search(self, responder, hostname):
        with FixtureProxy(responder) as proxy:
            uri_opener = proxy.opener()
            self.addCleanup(uri_opener.end)
            return pks(uri_opener).search(hostname), proxy

    def test_get_result(self):
        with self.assertLogs(
            "w3af.core.data.search_engines.pks", level="DEBUG"
        ) as logs:
            result, proxy = self.search(lambda url: BODY, "bonsai-sec.com")

        self.assertEqual([r.username for r in result], ["lucas", "nahuel"])
        self.assertEqual(result[0].name, "Lucas Apa (Bonsai Security Consultant)")
        self.assertEqual(result[0].domain, "bonsai-sec.com")
        self.assertIsNotNone(result[0].id)
        self.assertIn("returned 2 results", logs.output[0])

        request = proxy.requests[0]
        self.assertEqual(request.netloc, "pgp.mit.edu:11371")
        self.assertEqual(proxy.query(), {"op": "index", "search": "bonsai-sec.com"})

    def test_unreachable_server(self):
        result, _ = self.search(lambda url: DROP_CONNECTION, "bonsai-sec.com")

        self.assertEqual(result, [])

    def test_requires_root_domain(self):
        self.assertRaises(
            BaseFrameworkException, pks(None).search, "http://bonsai-sec.com"
        )

    def test_result_repr(self):
        result = PKSResult("Lucas", "lucas", "bonsai-sec.com", 1)

        self.assertEqual(repr(result), "<PKSResult: Lucas@bonsai-sec.com>")
