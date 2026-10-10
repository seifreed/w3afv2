"""
test_404_errors.py

Copyright 2015 Andres Riancho

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

import w3af.core.controllers.output_manager as om
import w3af.core.data.kb.knowledge_base as kb
from w3af.core.controllers.core_helpers.fingerprint_404 import (
    fingerprint_404_singleton,
)
from w3af.core.controllers.tests.local_http_server import closed_local_port
from w3af.core.controllers.tests.recording_output import start_recording_output
from w3af.core.data.dc.headers import Headers
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.request.fuzzable_request import FuzzableRequest
from w3af.core.data.url.extended_urllib import ExtendedUrllib
from w3af.core.data.url.http_response import HTTPResponse
from w3af.core.filesystem import create_temp_dir
from w3af.plugins.grep.meta_tags import meta_tags


class FailingURLOpener:
    """
    URL opener which fails every request with an unexpected error, the kind of
    bug that the 404 detection must not hide.
    """

    def __init__(self, message):
        self.message = message

    def GET(self, url, **kwargs):
        raise RuntimeError(self.message)


class Test404Errors(unittest.TestCase):
    def setUp(self):
        create_temp_dir()
        kb.kb.cleanup()
        self.plugin = meta_tags()
        self.plugin.set_output(om.out)
        self.fingerprint_404 = fingerprint_404_singleton(om.out, cleanup=True)

    def tearDown(self):
        kb.kb.cleanup()
        fingerprint_404_singleton(cleanup=True)

    def get_request_response(self):
        # The target port is closed: the 404 detection needs to send HTTP
        # requests to it in order to decide if this response is a 404
        body = '<meta test="user/pass"></script>'
        url = URL(f"http://127.0.0.1:{closed_local_port()}/")
        headers = Headers([("content-type", "text/html")])
        request = FuzzableRequest(url, method="GET")
        resp = HTTPResponse(200, body, headers, url, url, _id=1)
        return request, resp

    def test_handles_404_exception(self):
        uri_opener = ExtendedUrllib()
        self.fingerprint_404.set_url_opener(uri_opener)
        recorder = start_recording_output()
        request, resp = self.get_request_response()

        try:
            self.plugin.grep_wrapper(request, resp)
        finally:
            uri_opener.end()

        msg = 'Exception found while detecting 404: "'
        detection_errors = [
            message
            for message in recorder.messages_of("debug")
            if message.startswith(msg)
        ]
        vulns = kb.kb.get("meta_tags", "meta_tags")

        self.assertNotEqual(detection_errors, [])
        self.assertEqual(vulns, [])

    def test_raises_other_exceptions(self):
        msg = "Foos and bars"
        self.fingerprint_404.set_url_opener(FailingURLOpener(msg))
        request, resp = self.get_request_response()

        try:
            self.plugin.grep_wrapper(request, resp)
        except RuntimeError as e:
            self.assertEqual(str(e), msg)
        else:
            self.assertTrue(False, "Expected exception, success found!")
