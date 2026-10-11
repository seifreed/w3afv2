"""Tests for scan resource lifecycle cleanup."""

import unittest

from w3af.core.controllers.w3af_core import w3afCore
from w3af.core.ui.api.db.master import ScanInfo
from w3af.core.ui.api.utils.log_handler import RESTAPIOutput


class ScanInfoTest(unittest.TestCase):
    def test_cleanup_releases_core_and_output_resources(self):
        scan_info = ScanInfo()
        scan_info.w3af_core = w3afCore()
        scan_info.output = RESTAPIOutput()
        manager = scan_info.w3af_core._output_manager

        scan_info.cleanup()

        self.assertFalse(manager.is_alive())
        self.assertIsNone(scan_info.w3af_core)
        self.assertIsNone(scan_info.output)
