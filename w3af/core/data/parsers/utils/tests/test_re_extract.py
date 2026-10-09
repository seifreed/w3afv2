"""
test_re_extract.py

Copyright 2019 Andres Riancho

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

from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.parsers.utils.re_extract import ReExtract


class TestReExtract(unittest.TestCase):
    def test_relative_regex(self):
        doc_string = "123 ../../foobar/uploads/foo.png 465"
        base_url = URL("https://w3af.org/abc/def/")

        re_extract = ReExtract(doc_string, base_url, "utf-8")
        re_extract.parse()

        references = re_extract.get_references()

        self.assertEqual(references, [URL("https://w3af.org/foobar/uploads/foo.png")])

    def references(self, doc_string, **kwargs):
        re_extract = ReExtract(doc_string, URL("http://w3af.org/a/"), "utf-8", **kwargs)
        re_extract.parse()
        return set(re_extract.get_references())

    def test_require_quotes(self):
        doc_string = (
            "var a = 'http://w3af.org/quoted'; http://w3af.org/bare "
            'b = "/rel/quoted.php"; /rel/bare.php http://w3af.org/end'
        )

        self.assertEqual(
            self.references(doc_string, require_quotes=True),
            {URL("http://w3af.org/quoted"), URL("http://w3af.org/rel/quoted.php")},
        )

    def test_invalid_full_url_is_ignored(self):
        self.assertEqual(self.references("go to http://w3af.org:abc/x now"), set())

    def test_relative_false_positives(self):
        doc_string = "see ://w3af.org/a.php or //cdn.w3af.org/b.php or Apache/2.2.8.so"

        self.assertEqual(self.references(doc_string), set())

    def test_relative_disabled(self):
        self.assertEqual(self.references("/rel/bare.php", relative=False), set())
