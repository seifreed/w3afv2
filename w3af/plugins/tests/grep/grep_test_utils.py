"""
grep_test_utils.py

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

Shared helpers for the grep plugin unit tests.
"""

import unittest
from queue import Queue

from w3af.core.controllers.core_helpers.fingerprint_404 import Fingerprint404
from w3af.core.controllers.output_manager.log_sink import LogSink
from w3af.core.data.dc.headers import Headers
from w3af.core.data.kb.config import Config
from w3af.core.data.kb.knowledge_base import DBKnowledgeBase
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.parsers.parser_cache import ParserCache
from w3af.core.data.parsers.utils.response_uniq_id import get_response_unique_id
from w3af.core.data.request.fuzzable_request import FuzzableRequest
from w3af.core.data.url.http_response import HTTPResponse
from w3af.core.filesystem import create_temp_dir


def make_response(
    url="http://www.w3af.com/",
    body="<html><body>hello</body></html>",
    code=200,
    content_type="text/html",
    headers=(),
    _id=1,
    parser_cache=None,
):
    url = URL(url) if isinstance(url, str) else url
    all_headers = Headers([("content-type", content_type), *headers])
    cache = TEST_PARSER_CACHE if parser_cache is None else parser_cache
    return HTTPResponse(code, body, all_headers, url, url, _id=_id, parser_cache=cache)


def make_request(url="http://www.w3af.com/", method="GET", headers=()):
    url = URL(url) if isinstance(url, str) else url
    return FuzzableRequest(url, method=method, headers=Headers(list(headers)))


class GrepPluginTestCase(unittest.TestCase):
    """
    Base class which gives each test a clean knowledge base and restores any
    framework configuration the test changes.
    """

    def setUp(self):
        create_temp_dir()
        kb.cleanup()
        TEST_PARSER_CACHE.clear()
        self._fingerprint_404_detectors = []

    def tearDown(self):
        for detector in self._fingerprint_404_detectors:
            detector.cleanup()
        TEST_PARSER_CACHE.clear()
        kb.cleanup()

    def configure_plugin(self, plugin):
        plugin.set_knowledge_base(kb)
        plugin.set_configuration(cf)
        plugin.set_parser_cache(TEST_PARSER_CACHE)
        output = LogSink(Queue())
        plugin.set_output(output)
        detector = Fingerprint404(output, cf)
        plugin.set_fingerprint_404(detector)
        self._fingerprint_404_detectors.append(detector)
        return plugin

    def save_config(self, name, value):
        self.addCleanup(cf.save, name, cf.get(name))
        cf.save(name, value)

    def make_unparseable_response(self, **kwargs):
        """
        :return: A text/html response that the document parser refuses to
                 parse, exactly like a response which previously exceeded the
                 parser timeout and was blacklisted by the parser cache. The
                 body is unique per test so the blacklist does not leak.
        """
        kwargs.setdefault("body", f"<html>{self.id()}</html>")
        response = make_response(**kwargs)
        TEST_PARSER_CACHE.add_to_blacklist(get_response_unique_id(response))
        return response

    def mark_as_404(self, marker="ThisIsA404Page"):
        """
        Make fingerprint_404.is_404() treat responses containing `marker` as
        404 pages, using the user facing `string_match_404` setting.
        """
        self.save_config("string_match_404", marker)
        return marker


cf = Config()


kb = DBKnowledgeBase()


TEST_PARSER_CACHE = ParserCache()
