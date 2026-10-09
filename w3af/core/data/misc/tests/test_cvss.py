"""Tests for the CVSS to w3af severity mapping."""

import unittest

from w3af.core.data.constants import severity
from w3af.core.data.misc.cvss import cvss_to_severity


class TestCVSSToSeverity(unittest.TestCase):
    def test_mapping(self):
        expected = (
            (0, severity.INFORMATION),
            (1.9, severity.INFORMATION),
            (2, severity.LOW),
            (2.9, severity.LOW),
            (3, severity.MEDIUM),
            (6.9, severity.MEDIUM),
            (7, severity.HIGH),
            (7.75, severity.HIGH),
            (10, severity.HIGH),
        )

        for score, expected_severity in expected:
            with self.subTest(score=score):
                self.assertEqual(cvss_to_severity(score), expected_severity)
