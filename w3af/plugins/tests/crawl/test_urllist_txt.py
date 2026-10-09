"""
test_urllist_txt.py

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

from w3af.plugins.crawl.urllist_txt import urllist_txt
from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest

URLLIST_TXT = """# URLs for the Yahoo crawler

http://mock/hidden/
/hidden/
http://[broken
"""

HTML_PAGE = """<html>
<body>
<p>
Not a urllist</p>
</body>
</html>
"""

PLUGINS = {"crawl": (PluginConfig("urllist_txt"),)}


class TestURLListTxt(PluginTest):

    target_url = "http://mock/w3af/"

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse("http://mock/w3af/", "index"),
        MockResponse("http://mock/urllist.txt", URLLIST_TXT, "text/plain"),
        MockResponse("http://mock/hidden/", "hidden"),
    ]

    def test_urllist_txt(self):
        self._scan(self.target_url, PLUGINS)

        infos = self.kb.get("urllist_txt", "urllist.txt")
        self.assertEqual(len(infos), 1, infos)

        info = infos[0]
        self.assertTrue(info.get_name().startswith("urllist.txt file"))
        self.assertEqual(info.get_url().url_string, "http://mock/urllist.txt")

        urls = {u.url_string for u in self.kb.get_all_known_urls()}
        self.assertEqual(urls, {"http://mock/w3af/", "http://mock/hidden/"})


class TestURLListTxtMissing(PluginTest):

    target_url = "http://mock/w3af/"

    MOCK_RESPONSES: ClassVar[list] = [MockResponse("http://mock/w3af/", "index")]

    def test_no_urllist_txt(self):
        self._scan(self.target_url, PLUGINS)

        self.assertEqual(self.kb.get("urllist_txt", "urllist.txt"), [])


class TestURLListTxtIsHTML(PluginTest):

    target_url = "http://mock/w3af/"

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse("http://mock/w3af/", "index"),
        MockResponse("http://mock/urllist.txt", HTML_PAGE),
    ]

    def test_html_is_not_urllist_txt(self):
        self._scan(self.target_url, PLUGINS)

        self.assertEqual(self.kb.get("urllist_txt", "urllist.txt"), [])


def test_urllist_txt_long_desc():
    assert "urllist.txt" in urllist_txt().get_long_desc()
