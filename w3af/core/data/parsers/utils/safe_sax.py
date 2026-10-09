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
from xml.sax.handler import ContentHandler, ErrorHandler

from defusedxml import DefusedXmlException
from defusedxml import sax as defused_sax

# ContentHandler is re-exported: event handlers for the hardened parser below
# subclass the standard library one and override only the events they need
__all__ = ["ContentHandler", "XMLParseError", "parse_file", "parse_string"]


class XMLParseError(ValueError):
    """Raised when a document is not well-formed or uses forbidden XML
    features such as entity expansion or external references."""


class _RaisingErrorHandler(ErrorHandler):
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
