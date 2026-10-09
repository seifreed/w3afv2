"""
safe_sax.py

Copyright 2024 Andres Riancho

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

from defusedxml import DefusedXmlException
from defusedxml import sax as defused_sax


class XMLParseError(ValueError):
    """Raised when a document is not well-formed or uses forbidden XML
    features such as entity expansion or external references."""


class ContentHandler:
    """
    Base class for SAX event handlers driven by the hardened parser below.
    Subclasses override only the events they care about.
    """

    def setDocumentLocator(self, locator):
        pass

    def startDocument(self):
        pass

    def endDocument(self):
        pass

    def startPrefixMapping(self, prefix, uri):
        pass

    def endPrefixMapping(self, prefix):
        pass

    def startElement(self, name, attrs):
        pass

    def endElement(self, name):
        pass

    def startElementNS(self, name, qname, attrs):
        pass

    def endElementNS(self, name, qname):
        pass

    def characters(self, content):
        pass

    def ignorableWhitespace(self, whitespace):
        pass

    def processingInstruction(self, target, data):
        pass

    def skippedEntity(self, name):
        pass


class _RaisingErrorHandler:
    def warning(self, exception):
        pass

    def error(self, exception):
        raise XMLParseError(str(exception)) from exception

    def fatalError(self, exception):
        raise XMLParseError(str(exception)) from exception


def parse_string(xml_string, handler):
    """
    Parse ``xml_string`` (str or bytes) with a parser that rejects entity
    expansion and external references, feeding the events to ``handler``.

    :raises XMLParseError: When the document is malformed or unsafe.
    """
    if isinstance(xml_string, str):
        parse_file(io.StringIO(xml_string), handler)
    else:
        parse_file(io.BytesIO(xml_string), handler)


def parse_file(file_obj, handler):
    """
    Same as parse_string() but reads the document from an open file.

    :raises XMLParseError: When the document is malformed or unsafe.
    """
    parser = defused_sax.make_parser()
    parser.setContentHandler(handler)
    parser.setErrorHandler(_RaisingErrorHandler())

    try:
        parser.parse(file_obj)
    except DefusedXmlException as error:
        raise XMLParseError(str(error)) from error
