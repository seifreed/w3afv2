import unittest

import pytest

import w3af.core.controllers.output_manager as om
from w3af.core.controllers.delay_detection.exact_delay import ExactDelay
from w3af.core.controllers.delay_detection.exact_delay_controller import (
    ExactDelayController,
)
from w3af.core.controllers.sql_tools.blind_sqli_time_delay import BlindSQLTimeDelay
from w3af.core.controllers.sql_tools.tests.blind_sqli_sites import (
    SlowSql,
    mutant_for,
    static_page,
)
from w3af.core.data.constants import severity
from w3af.core.data.url.extended_urllib import ExtendedUrllib
from w3af.core.data.url.tests.helpers.route_server import RouteServer

POSTGRESQL_DELAY = ExactDelay("1 or pg_sleep(%s)")


class BlindSQLTimeDelayTestCase(unittest.TestCase):
    def setUp(self):
        self.uri_opener = ExtendedUrllib()
        self.addCleanup(self.uri_opener.end)
        self.addCleanup(self.uri_opener.settings.set_default_values)
        self.detector = BlindSQLTimeDelay(self.uri_opener, om.out)
        self.detector.set_debugging_id(7)


class TestBlindSQLTimeDelayConfiguration(BlindSQLTimeDelayTestCase):
    def test_debugging_id(self):
        self.assertEqual(self.detector.get_debugging_id(), 7)

    def test_debugging_id_is_unset_by_default(self):
        self.assertIsNone(BlindSQLTimeDelay(self.uri_opener, om.out).get_debugging_id())

    def test_repr_includes_the_debugging_id(self):
        self.assertEqual(repr(self.detector), "<BlindSQLTimeDelay did=7>")

    def test_delays_cover_the_supported_databases(self):
        delays = self.detector.get_delays()

        self.assertTrue(all(isinstance(delay, ExactDelay) for delay in delays))
        payloads = [delay.get_string_for_delay(5) for delay in delays]
        self.assertIn("1;waitfor delay '0:0:5'--", payloads)
        self.assertIn("1 AND (SELECT * FROM (SELECT(SLEEP(5)))foo)", payloads)
        self.assertIn("1 or pg_sleep(5)", payloads)


class TestBlindSQLTimeDelayDetection(BlindSQLTimeDelayTestCase):
    def test_server_that_does_not_delay_is_not_injectable(self):
        server = RouteServer.serve_for(self, {"/page": static_page})

        vuln = self.detector.is_injectable(
            mutant_for(server, "/page"), POSTGRESQL_DELAY
        )

        self.assertIsNone(vuln)

    @pytest.mark.slow
    def test_server_that_sleeps_as_requested_is_injectable(self):
        server = RouteServer.serve_for(self, {"/page": SlowSql()})
        mutant = mutant_for(server, "/page")

        vuln = self.detector.is_injectable(mutant, POSTGRESQL_DELAY)

        self.assertIsNotNone(vuln)
        self.assertEqual(vuln.get_name(), "Blind SQL injection vulnerability")
        self.assertEqual(vuln.get_severity(), severity.HIGH)
        self.assertEqual(vuln.get_plugin_name(), "blind_sqli")
        self.assertEqual(vuln.get_mutant().get_token_name(), "id")
        self.assertIn(
            "Blind SQL injection using time delays was found at:", vuln.get_desc()
        )
        self.assertEqual(len(vuln.get_id()), len(ExactDelayController.DELAY_SECONDS))
