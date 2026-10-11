"""
test_xmlrpc.py

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

import html
import unittest

from w3af.core.data.dc.utils.token import DataToken
from w3af.core.data.parsers.doc.xmlrpc import (
    XmlRpcReadHandler,
    XmlRpcWriteHandler,
    build_xmlrpc,
    parse_xmlrpc,
)
from w3af.core.data.parsers.utils.safe_sax import parse_string

XML_WITH_FUZZABLE = """\
<methodCall>
   <methodName>sample.sum</methodName>
   <params>
       <param>
           <array>
              <data>
                 <value><i4>1404</i4></value>
                 <value><string>Foo bar</string></value>
                 <value><i4>1</i4></value>
                 <value><base64>U3BhbSBlZ2dz</base64></value>
              </data>
           </array>
       </param>
   </params>
</methodCall>"""

XML_WITHOUT_FUZZABLE = """\
<methodCall>
   <methodName>sample.sum</methodName>
   <params>
       <param>
           <array>
               <data>
                   <value><i4>1404</i4></value>
                   <value><i4>1</i4></value>
               </data>
           </array>
       </param>
   </params>
</methodCall>"""


class TestXMLRPC(unittest.TestCase):

    def test_reader(self):
        handler = XmlRpcReadHandler()
        parse_string(XML_WITH_FUZZABLE, handler)

        EXPECTED = [("string", ["Foo bar"]), ("base64", ["Spam eggs"])]

        self.assertEqual(list(handler.get_data_container().items()), EXPECTED)

    def test_writer(self):
        handler = XmlRpcReadHandler()
        parse_string(XML_WITH_FUZZABLE, handler)

        data_container = handler.get_data_container()
        payload = "<script>alert(1)</script>"
        data_container["string"][0] = payload

        writer = XmlRpcWriteHandler(data_container)

        fuzzed = XML_WITH_FUZZABLE.replace("Foo bar", html.escape(payload, quote=False))

        parse_string(XML_WITH_FUZZABLE, writer)
        self.assertEqual(writer.fuzzed_xml_string, fuzzed)

    def test_parse_and_build_with_tokens_and_attributes(self):
        xml_string = (
            '<methodCall><methodName lang="en">sample.sum</methodName>'
            "<params><param><value><string>Foo</string></value></param>"
            "</params></methodCall>"
        )

        data_container = parse_xmlrpc(xml_string).get_data_container()
        data_container["string"][0] = DataToken("string", "<b>bar</b>", ("string", 0))

        self.assertEqual(
            build_xmlrpc(xml_string, data_container),
            xml_string.replace("Foo", "&lt;b&gt;bar&lt;/b&gt;"),
        )
