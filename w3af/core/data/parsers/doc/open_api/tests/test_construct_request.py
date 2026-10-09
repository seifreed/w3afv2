"""
test_construct_request.py

Copyright 2026 w3af contributors

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

from bravado_core.exception import SwaggerMappingError

from w3af.core.data.parsers.doc.open_api.construct_request import construct_request
from w3af.core.data.parsers.doc.open_api.relaxed_spec import (
    RelaxedSpec,
    validate_generic,
)

SPEC = {
    "swagger": "2.0",
    "info": {"title": "construct request", "version": "1.0.0"},
    "host": "w3af.org",
    "basePath": "/api/",
    "paths": {
        "/pets": {
            "get": {
                "operationId": "listPets",
                "parameters": [
                    {"name": "kind", "in": "query", "type": "string", "required": True},
                    {"name": "limit", "in": "query", "type": "integer", "default": 10},
                    {"name": "page", "in": "query", "type": "integer"},
                    {
                        "name": "trace",
                        "in": "query",
                        "type": "string",
                        "format": "uuid-v9",
                    },
                ],
                "responses": {"200": {"description": "pets"}},
            }
        }
    },
}

CONFIG = {
    "use_models": False,
    "validate_swagger_spec": False,
    "validate_requests": False,
    "validate_responses": False,
}


class TestConstructRequest(unittest.TestCase):

    def setUp(self):
        spec = RelaxedSpec.from_dict(
            SPEC, origin_url="http://w3af.org/swagger.json", config=CONFIG
        )
        self.operation = spec.resources["pets"].operations["listPets"]

    def test_optional_parameters_are_not_sent(self):
        request = construct_request(self.operation, kind="cat")

        self.assertEqual(request["method"], "GET")
        self.assertEqual(request["url"], "http://w3af.org/api/pets")
        self.assertEqual(request["params"], {"kind": "cat"})

    def test_passed_parameters_are_marshalled(self):
        request = construct_request(self.operation, kind="cat", limit=5, page=2)

        self.assertEqual(request["params"], {"kind": "cat", "limit": "5", "page": "2"})
        self.assertEqual(request["headers"], {})

    def test_unknown_parameter(self):
        with self.assertRaisesRegex(SwaggerMappingError, "does not have parameter"):
            construct_request(self.operation, kind="cat", color="black")

    def test_missing_required_parameter(self):
        with self.assertRaisesRegex(SwaggerMappingError, "kind is a required"):
            construct_request(self.operation)


class TestRelaxedSpec(unittest.TestCase):

    def test_custom_formats_are_accepted(self):
        spec = RelaxedSpec.from_dict(
            SPEC, origin_url="http://w3af.org/swagger.json", config=CONFIG
        )

        generic = spec.get_format("uuid-v9")

        self.assertEqual(generic.format, "uuid-v9")
        self.assertEqual(generic.to_wire("abc"), "abc")
        self.assertEqual(generic.to_python("abc"), "abc")
        self.assertIs(generic.validate, validate_generic)
        self.assertTrue(generic.validate("anything at all"))

    def test_default_formats_are_kept(self):
        spec = RelaxedSpec.from_dict(
            SPEC, origin_url="http://w3af.org/swagger.json", config=CONFIG
        )

        self.assertEqual(spec.get_format("int64").format, "int64")
