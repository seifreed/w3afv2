"""Tests for generated OpenAPI parameter values."""

import unittest

from w3af.core.data.parsers.doc.open_api.parameters import ParameterHandler
from w3af.core.data.parsers.doc.open_api.relaxed_spec import RelaxedSpec


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


SPEC_CONFIG = {
    "use_models": False,
    "validate_swagger_spec": False,
    "validate_requests": False,
    "validate_responses": False,
}


def operation_with(parameters, definitions=None):
    spec_dict = {
        "swagger": "2.0",
        "info": {"title": "parameters", "version": "1.0.0"},
        "host": "w3af.org",
        "paths": {
            "/items": {
                "post": {
                    "operationId": "addItem",
                    "parameters": parameters,
                    "responses": {"200": {"description": "ok"}},
                }
            }
        },
        "definitions": definitions or {},
    }
    spec = RelaxedSpec.from_dict(
        spec_dict, origin_url="http://w3af.org/swagger.json", config=SPEC_CONFIG
    )
    return spec, spec.resources["items"].operations["addItem"]


def filled(parameters, definitions=None, optional=True):
    spec, operation = operation_with(parameters, definitions)
    handler = ParameterHandler(spec, operation)
    filled_operation = handler.set_operation_params(optional=optional)
    return handler, {name: p.fill for name, p in filled_operation.params.items()}


class TestParameterHandlerFixes(unittest.TestCase):

    def test_string_with_numeric_or_string_format_loses_the_format(self):
        handler, _ = filled(
            [
                {"name": "sort", "in": "query", "type": "string", "format": "string"},
                {"name": "ids", "in": "query", "type": "string", "format": "int64"},
            ]
        )

        params = handler.operation.params
        self.assertNotIn("format", params["sort"].param_spec)
        self.assertNotIn("format", params["ids"].param_spec)

    def test_invalid_number_defaults_and_examples_become_zero(self):
        handler, values = filled(
            [
                {
                    "name": "a",
                    "in": "query",
                    "type": "integer",
                    "format": "int64",
                    "default": "",
                },
                {
                    "name": "b",
                    "in": "query",
                    "type": "integer",
                    "format": "int64",
                    "default": "7",
                },
                {
                    "name": "c",
                    "in": "query",
                    "type": "integer",
                    "format": "int32",
                    "example": "x",
                },
                {
                    "name": "d",
                    "in": "query",
                    "type": "integer",
                    "format": "int32",
                    "example": "3",
                },
            ]
        )

        specs = {name: p.param_spec for name, p in handler.operation.params.items()}
        self.assertEqual(specs["a"]["default"], 0)
        self.assertEqual(specs["b"]["default"], "7")
        self.assertEqual(specs["c"]["example"], 0)
        self.assertEqual(specs["d"]["example"], "3")
        self.assertEqual(values["b"], "7")


class TestParameterHandlerValues(unittest.TestCase):

    def test_array_without_items_is_empty(self):
        _, values = filled(
            [{"name": "tags", "in": "body", "schema": {"type": "array"}}]
        )

        self.assertEqual(values["tags"], [])

    def test_schema_without_type_is_an_empty_object(self):
        _, values = filled([{"name": "payload", "in": "body", "schema": {}}])

        self.assertEqual(values["payload"], {})

    def test_all_of_part_with_inline_and_referenced_schema(self):
        definitions = {
            "Named": {"type": "object", "properties": {"name": {"type": "string"}}},
        }
        schema = {
            "allOf": [
                {"schema": {"$ref": "#/definitions/Named"}},
                {
                    "schema": {
                        "type": "object",
                        "properties": {"age": {"type": "integer"}},
                    }
                },
            ]
        }

        _, values = filled(
            [{"name": "pet", "in": "body", "schema": schema}], definitions
        )

        self.assertEqual(set(values["pet"]), {"name", "age"})
        self.assertEqual(values["pet"]["age"], 42)

    def test_header_with_schema_default_is_always_filled(self):
        _, values = filled(
            [
                {
                    "name": "X-Api",
                    "in": "header",
                    "type": "string",
                    "schema": {"default": "v2"},
                },
                {"name": "q", "in": "query", "type": "string"},
            ],
            optional=False,
        )

        # bravado-core sanitizes the parameter name
        self.assertIsNotNone(values["X_Api"])
        self.assertIsNone(values["q"])
