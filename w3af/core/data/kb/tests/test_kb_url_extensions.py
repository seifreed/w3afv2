"""
test_kb_url_extensions.py

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

import unittest

from w3af.core.data.kb.kb_url_extensions import get_url_extensions_from_kb
from w3af.core.data.kb.knowledge_base import kb
from w3af.core.data.parsers.doc.url import URL


class TestKBURLExtensions(unittest.TestCase):
    def setUp(self):
        kb.cleanup()
        self.addCleanup(kb.cleanup)

    def test_no_urls(self):
        self.assertEqual(get_url_extensions_from_kb(), set())

    def test_extensions(self):
        for url in (
            "http://w3af.org/index.php",
            "http://w3af.org/login.php?user=1",
            "http://w3af.org/static/app.js",
            "http://w3af.org/about/",
        ):
            kb.add_url(URL(url))

        self.assertEqual(get_url_extensions_from_kb(), {"php", "js", ""})
