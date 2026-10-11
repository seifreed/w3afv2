"""Tests for the scan-level 404 detector lifecycle."""

import unittest

from w3af.core.controllers.core_helpers.fingerprint_404_lifecycle import (
    Fingerprint404Lifecycle,
)
from w3af.core.controllers.output_manager import create_output_manager
from w3af.core.data.db.dbms import create_temp_db_instance
from w3af.core.data.kb.config import Config
from w3af.core.data.url.extended_urllib import ExtendedUrllib
from w3af.core.data.url.http_response import HTTPResponse
from w3af.core.data.dc.headers import Headers
from w3af.core.data.parsers.doc.url import URL


class TestFingerprint404Lifecycle(unittest.TestCase):
    def setUp(self):
        self.manager, self.output = create_output_manager()
        self.database = create_temp_db_instance()
        self.opener = ExtendedUrllib()
        self.lifecycle = Fingerprint404Lifecycle(
            self.output,
            Config(),
            self.database,
            self.opener,
        )
        self.addCleanup(self.manager.stop)
        self.addCleanup(self.database.close)
        self.addCleanup(self.opener.end)
        self.addCleanup(self.lifecycle.cleanup)

    def response(self, code):
        url = URL("http://example.com/")
        return HTTPResponse(code, "", Headers(), url, url, _id=1)

    def test_is_404_lazily_starts_the_detector(self):
        self.assertTrue(self.lifecycle.is_404(self.response(404)))

    def test_start_replaces_and_cleanup_releases_the_detector(self):
        self.lifecycle.start()
        self.lifecycle.start()
        self.lifecycle.cleanup()

        self.assertTrue(self.lifecycle.is_404(self.response(404)))
