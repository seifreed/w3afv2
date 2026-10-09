"""
example_specifications.py

Copyright 2018 Andres Riancho

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

import json
from pathlib import Path

CURRENT_PATH = Path(__file__).parent


def _read_specification(filename):
    return (CURRENT_PATH / "data" / filename).read_text(encoding="utf-8")


def _swagger_2_specification(title, paths):
    return json.dumps(
        {
            "swagger": "2.0",
            "info": {"title": title, "version": "1.0.0"},
            "paths": paths,
        },
        indent=4,
    )


class IntParamQueryString:
    def get_specification(self):
        return _read_specification("int_param_qs.json")


class StringParamJson:
    def get_specification(self):
        return _read_specification("string_param_json.json")


class IntParamJson:
    def get_specification(self):
        return _read_specification("int_param_json.json")


class IntParamWithExampleJson:
    def get_specification(self):
        return _read_specification("int_param_with_example_json.json")


class IntParamNoModelJson:
    def get_specification(self):
        return _read_specification("int_param_no_model_json.json")


class ComplexDereferencedNestedModel:
    def get_specification(self):
        return _read_specification("complex_dereferenced_nested_model.json")


class DereferencedPetStore:
    def get_specification(self):
        return _read_specification("dereferenced_pet_store.json")


class NestedModel:
    def get_specification(self):
        return _read_specification("nested_model.json")


class NestedLoopModel:
    def get_specification(self):
        return _read_specification("nested_loop_model.json")


class StringParamHeader:
    def get_specification(self):
        return _read_specification("string_param_header.json")


class MultiplePathsAndHeaders:
    def get_specification(self):
        return _read_specification("multiple_paths_and_headers.json")


class PetstoreSimpleModel:

    @staticmethod
    def get_specification():
        return _read_specification("petstore-simple.json")


class IntParamPath:
    def get_specification(self):
        return _swagger_2_specification(
            self.__class__.__name__,
            {
                "/pets/{pet_id}": {
                    "get": {
                        "operationId": "get_pets_pet_id",
                        "parameters": [
                            {
                                "name": "pet_id",
                                "in": "path",
                                "required": True,
                                "type": "integer",
                                "format": "int32",
                            }
                        ],
                        "responses": {"200": {"description": "Pet response"}},
                    }
                }
            },
        )


class StringParamQueryString:
    def get_specification(self):
        return _read_specification("string_param_qs.json")


class ArrayStringItemsQueryString:
    def get_specification(self):
        return _read_specification("array_string_items_qs.json")


class ArrayIntItemsQueryString:
    def get_specification(self):
        return _read_specification("array_int_items_qs.json")


class ArrayModelItems:
    def get_specification(self):
        return _read_specification("array_model_items_json.json")


class NoParams:

    def get_specification(self):
        return _swagger_2_specification(
            self.__class__.__name__,
            {"/random": {"get": {"operationId": "get_random", "responses": {}}}},
        )
