import unittest

from w3af.plugins.output.system_log import system_log


class TestSystemLog(unittest.TestCase):

    def setUp(self):
        self.plugin = system_log()

    def test_message_contains_scan_id(self):
        self.plugin.scan_id = "scan-1"

        expected = "[scan-1] hello\nworld"
        self.assertEqual(self.plugin._create_message("hello\nworld"), expected)

    def test_plugin_metadata(self):
        self.assertEqual(self.plugin.get_name(), "system_log")
        self.assertEqual(self.plugin.get_type(), "output")
        self.assertIn("syslog", self.plugin.get_long_desc())

    def test_default_options(self):
        options = self.plugin.get_options()

        self.assertFalse(options["verbose"].get_value())
        self.assertEqual(options["scan_id"].get_value(), "")
