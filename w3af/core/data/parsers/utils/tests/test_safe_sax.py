"""
test_safe_sax.py

Copyright 2026 w3af contributors

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

import io
import unittest

from w3af.core.data.parsers.utils.safe_sax import (
    ContentHandler,
    XMLParseError,
    parse_file,
    parse_string,
)

ENTITY_EXPANSION = """<?xml version="1.0"?>
<!DOCTYPE lolz [
  <!ENTITY lol "lol">
  <!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">
]>
<lolz>&lol2;</lolz>
"""

EXTERNAL_ENTITY = """<?xml version="1.0"?>
<!DOCTYPE foo [<!ENTITY ext SYSTEM "file:///etc/hosts">]>
<foo>&ext;</foo>
"""


class RecordingHandler(ContentHandler):
    def __init__(self):
        ContentHandler.__init__(self)
        self.events = []

    def startElement(self, name, attrs):
        self.events.append(("start", name, dict(attrs)))

    def characters(self, content):
        self.events.append(("text", content))

    def endElement(self, name):
        self.events.append(("end", name))


DOCUMENT = '<methodCall><name lang="en">ping</name></methodCall>'
EXPECTED = [
    ("start", "methodCall", {}),
    ("start", "name", {"lang": "en"}),
    ("text", "ping"),
    ("end", "name"),
    ("end", "methodCall"),
]


class TestSafeSAX(unittest.TestCase):

    @staticmethod
    def events(parse, document):
        handler = RecordingHandler()
        parse(document, handler)
        return handler.events

    def test_parse_text(self):
        self.assertEqual(self.events(parse_string, DOCUMENT), EXPECTED)

    def test_parse_bytes(self):
        events = self.events(parse_string, DOCUMENT.encode("utf-8"))
        self.assertEqual(events, EXPECTED)

    def test_parse_file(self):
        events = self.events(parse_file, io.StringIO(DOCUMENT))
        self.assertEqual(events, EXPECTED)

    def test_malformed_document(self):
        with self.assertRaises(XMLParseError):
            parse_string("<open><unclosed></open>", RecordingHandler())

    def test_entity_expansion_is_rejected(self):
        with self.assertRaises(XMLParseError):
            parse_string(ENTITY_EXPANSION, RecordingHandler())

    def test_external_entity_is_rejected(self):
        with self.assertRaises(XMLParseError):
            parse_string(EXTERNAL_ENTITY, RecordingHandler())
