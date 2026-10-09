import logging
import unittest

from w3af.core import FilterScapy


def record(message):
    return logging.LogRecord("scapy.runtime", logging.WARNING, "", 0, message, (), None)


class TestFilterScapy(unittest.TestCase):
    def test_ipv6_route_messages_are_dropped(self):
        self.assertFalse(FilterScapy().filter(record("No route found for IPv6")))

    def test_other_messages_pass(self):
        self.assertTrue(FilterScapy().filter(record("Something else")))

    def test_filter_installed_on_scapy_logger(self):
        filters = logging.getLogger("scapy.runtime").filters

        self.assertTrue(any(isinstance(f, FilterScapy) for f in filters))
