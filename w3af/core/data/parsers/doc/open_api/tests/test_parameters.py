"""Tests for generated OpenAPI parameter values."""

import unittest

from w3af.core.data.parsers.doc.open_api.parameters import ParameterHandler


class TestParameterValueGeneration(unittest.TestCase):
    def setUp(self):
        self.parameter_handler = ParameterHandler({}, {})

    def test_integer_parameters_accept_decimal_schema_bounds(self):
        parameter_spec = {"minimum": 1.2, "maximum": 10.8}

        value = self.parameter_handler._get_param_value_for_type_and_spec(
            "integer", parameter_spec
        )

        self.assertIsInstance(value, int)
        self.assertGreaterEqual(value, 2)
        self.assertLessEqual(value, 10)
        self.assertEqual(
            value,
            self.parameter_handler._get_param_value_for_type_and_spec(
                "integer", parameter_spec
            ),
        )

    def test_float_parameters_generate_deterministic_values_within_bounds(self):
        parameter_spec = {"minimum": 0.25, "maximum": 2.75}

        value = self.parameter_handler._get_param_value_for_type_and_spec(
            "float", parameter_spec
        )

        self.assertIsInstance(value, float)
        self.assertGreaterEqual(value, 0.25)
        self.assertLessEqual(value, 2.75)
        self.assertEqual(
            value,
            self.parameter_handler._get_param_value_for_type_and_spec(
                "float", parameter_spec
            ),
        )
