"""
test_lang.py

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

from w3af.core.data.dc.headers import Headers
from w3af.core.data.kb.knowledge_base import DBKnowledgeBase
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.request.fuzzable_request import FuzzableRequest
from w3af.core.data.url.http_response import HTTPResponse
from w3af.core.filesystem import create_temp_dir
from w3af.plugins.grep.lang import lang

ENGLISH_TEXT = (
    "The quick brown fox jumps over the lazy dog while the sun is shining and"
    " the birds are singing in the trees near the river where children play"
    " every afternoon during the warm summer days of this wonderful year."
)

SPANISH_TEXT = (
    "El rapido zorro marron salta sobre el perro perezoso mientras el sol"
    " brilla y los pajaros cantan en los arboles cerca del rio donde los"
    " ninos juegan todas las tardes durante los calidos dias de verano de"
    " este maravilloso anio."
)


class TestLang(unittest.TestCase):

    def setUp(self):
        create_temp_dir()
        kb.cleanup()
        self.plugin = lang()
        self.plugin.set_knowledge_base(kb)
        self.url = URL("http://www.w3af.com/")
        self.request = FuzzableRequest(self.url)

    def tearDown(self):
        kb.cleanup()

    def _grep(self, text, content_type="text/html"):
        body = f"<html><body><p>{text}</p></body></html>"
        headers = Headers([("content-type", content_type)])
        response = HTTPResponse(200, body, headers, self.url, self.url, _id=1)
        self.plugin.grep(self.request, response)

    def test_id_en(self):
        self._grep(ENGLISH_TEXT)
        self.assertEqual("en", kb.raw_read("lang", "lang"))

    def test_id_es(self):
        self._grep(SPANISH_TEXT)
        self.assertEqual("es", kb.raw_read("lang", "lang"))

    def test_not_text_is_ignored(self):
        self._grep(ENGLISH_TEXT, content_type="image/png")
        self.assertEqual([], kb.raw_read("lang", "lang"))


kb = DBKnowledgeBase()
