"""
test_pks.py

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

import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from w3af.core.data.search_engines.pks import pks
from w3af.core.data.url.extended_urllib import ExtendedUrllib
from w3af.core.filesystem import create_temp_dir

#
# Good idea to update this every now and then using:
# wget 'http://pgp.mit.edu:11371/pks/lookup?op=index&search=bonsai-sec.com'
#
BODY = """\
<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd" >
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
<title>Search results for 'sec com bonsai'</title>
<meta http-equiv="Content-Type" content="text/html;charset=utf-8" />
<style type="text/css">
/*<![CDATA[*/
 .uid { color: green; text-decoration: underline; }
 .warn { color: red; font-weight: bold; }
/*]]>*/
</style></head><body><h1>Search results for 'sec com bonsai'</h1><pre>Type bits/keyID     Date       User ID
</pre><hr /><pre>
pub  2048R/<a href="/pks/lookup?op=get&amp;search=0x8C9D86461E9B9265">1E9B9265</a> 2010-05-06 <a href="/pks/lookup?op=vindex&amp;search=0x8C9D86461E9B9265">Lucas Apa (Bonsai Security Consultant) &lt;lucas@bonsai-sec.com&gt;</a>
</pre><hr /><pre>
pub  1024D/<a href="/pks/lookup?op=get&amp;search=0x3608ED24EB0B8821">EB0B8821</a> 2010-04-11 <a href="/pks/lookup?op=vindex&amp;search=0x3608ED24EB0B8821">Nahuel Grisolia &lt;nahuel@bonsai-sec.com&gt;</a>
</pre></body></html>
"""


class PKSLookupHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        request = urlparse(self.path)
        query = parse_qs(request.query)
        expected_query = {"op": ["index"], "search": ["bonsai-sec.com"]}

        if request.path != "/pks/lookup" or query != expected_query:
            self.send_error(404)
            return

        body = BODY.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


class TestPKS(unittest.TestCase):

    def setUp(self):
        create_temp_dir()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), PKSLookupHandler)
        self.server_thread = threading.Thread(
            target=self.server.serve_forever, daemon=True
        )
        self.server_thread.start()

        port = self.server.server_address[1]
        lookup_url = f"http://127.0.0.1:{port}/pks/lookup"
        self.uri_opener = ExtendedUrllib()
        self.pks_se = pks(self.uri_opener, lookup_url=lookup_url)

    def tearDown(self):
        self.uri_opener.end()
        self.server.shutdown()
        self.server.server_close()
        self.server_thread.join()

    def test_get_result(self):
        domain = "bonsai-sec.com"

        with self.assertLogs(
            "w3af.core.data.search_engines.pks", level="DEBUG"
        ) as logs:
            result = self.pks_se.search(domain)

        self.assertEqual(len(result), 2)
        self.assertIn("returned 2 results", logs.output[0])

        expected = {"lucas"}
        self.assertTrue({r.username for r in result}.issuperset(expected), result)
