# -*- coding: UTF-8 -*-
"""
test_specification.py

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

import datetime
import os
import tempfile
import unittest

from w3af.core.data.dc.headers import Headers
from w3af.core.data.parsers.doc.open_api.parameters import ParameterHandler
from w3af.core.data.parsers.doc.open_api.specification import SpecificationHandler
from w3af.core.data.parsers.doc.open_api.tests.example_specifications import (
    ArrayIntItemsQueryString,
    ArrayModelItems,
    ArrayStringItemsQueryString,
    ComplexDereferencedNestedModel,
    DereferencedPetStore,
    IntParamJson,
    IntParamNoModelJson,
    IntParamPath,
    IntParamQueryString,
    MultiplePathsAndHeaders,
    NestedLoopModel,
    NestedModel,
    NoParams,
    StringParamHeader,
    StringParamJson,
    StringParamQueryString,
)
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.url.http_response import HTTPResponse


class TestSpecification(unittest.TestCase):

    @staticmethod
    def generate_response(specification_as_string):
        url = URL("http://www.w3af.com/swagger.json")
        headers = Headers([("content-type", "application/json")])
        return HTTPResponse(200, specification_as_string, headers, url, url, _id=1)

    def test_no_params(self):
        specification_as_string = NoParams().get_specification()
        http_response = self.generate_response(specification_as_string)
        handler = SpecificationHandler(http_response)

        data = [d for d in handler.get_api_information()]

        self.assertEqual(len(data), 1)

        _spec, api_resource_name, _resource, operation_name, operation, _parameters = (
            data[0]
        )

        self.assertEqual(api_resource_name, "random")
        self.assertEqual(operation_name, "get_random")
        self.assertEqual(operation.consumes, [])
        self.assertEqual(operation.produces, [])
        self.assertEqual(operation.params, {})
        self.assertEqual(operation.path_name, "/random")

    def test_simple_int_param_in_qs(self):
        specification_as_string = IntParamQueryString().get_specification()
        http_response = self.generate_response(specification_as_string)
        handler = SpecificationHandler(http_response)

        data = [d for d in handler.get_api_information()]

        # The specification says that this query string parameter is not
        # required, thus we get two operations, one for the parameter with
        # a value and another without the parameter
        self.assertEqual(len(data), 2)

        _, api_resource_name, _, operation_name, operation, _ = data[0]

        self.assertEqual(api_resource_name, "pets")
        self.assertEqual(operation_name, "findPets")
        self.assertEqual(operation.consumes, ["application/json"])
        self.assertEqual(operation.produces, ["application/json"])
        self.assertEqual(operation.path_name, "/pets")

        # Now we check the parameters for the operation
        self.assertEqual(len(operation.params), 1)

        param = operation.params.get("limit")
        self.assertEqual(param.param_spec["required"], False)
        self.assertEqual(param.param_spec["in"], "query")
        self.assertEqual(param.param_spec["type"], "integer")
        self.assertEqual(param.fill, None)

        # And check the second one too
        _spec, api_resource_name, _resource, operation_name, operation, _parameters = (
            data[1]
        )

        self.assertEqual(len(operation.params), 1)

        param = operation.params.get("limit")
        self.assertEqual(param.param_spec["required"], False)
        self.assertEqual(param.param_spec["in"], "query")
        self.assertEqual(param.param_spec["type"], "integer")
        self.assertEqual(param.fill, 42)

    def test_simple_int_param_in_path(self):
        specification_as_string = IntParamPath().get_specification()
        http_response = self.generate_response(specification_as_string)
        handler = SpecificationHandler(http_response)

        data = [d for d in handler.get_api_information()]

        self.assertEqual(len(data), 1)

        _spec, api_resource_name, _resource, operation_name, operation, _parameters = (
            data[0]
        )

        self.assertEqual(api_resource_name, "pets")
        self.assertEqual(operation_name, "get_pets_pet_id")
        self.assertEqual(operation.consumes, [])
        self.assertEqual(operation.produces, [])
        self.assertEqual(operation.path_name, "/pets/{pet_id}")

        # And now the real stuff...
        self.assertEqual(len(operation.params), 1)

        param = operation.params.get("pet_id")
        self.assertEqual(param.param_spec["required"], True)
        self.assertEqual(param.param_spec["in"], "path")
        self.assertEqual(param.param_spec["type"], "integer")
        self.assertEqual(param.fill, 42)

    def test_simple_string_param_in_qs(self):
        specification_as_string = StringParamQueryString().get_specification()
        http_response = self.generate_response(specification_as_string)
        handler = SpecificationHandler(http_response)

        data = [d for d in handler.get_api_information()]

        # The specification says that this query string parameter is
        # required and there is only one parameter, so there is no second
        # operation with the optional parameters filled in.
        self.assertEqual(len(data), 1)

        _spec, api_resource_name, _resource, operation_name, operation, _parameters = (
            data[0]
        )

        self.assertEqual(api_resource_name, "pets")
        self.assertEqual(operation_name, "findPets")
        self.assertEqual(operation.consumes, ["application/json"])
        self.assertEqual(operation.produces, ["application/json"])
        self.assertEqual(operation.path_name, "/pets")

        # Now we check the parameters for the operation
        self.assertEqual(len(operation.params), 1)

        param = operation.params.get("q")
        self.assertEqual(param.param_spec["required"], True)
        self.assertEqual(param.param_spec["in"], "query")
        self.assertEqual(param.param_spec["type"], "string")
        self.assertEqual(param.fill, "Hello World")

    def test_string_param_header(self):
        specification_as_string = StringParamHeader().get_specification()
        http_response = self.generate_response(specification_as_string)
        handler = SpecificationHandler(http_response)

        data = [d for d in handler.get_api_information()]

        # The specification says that this query string parameter is
        # required and there is only one parameter, so there is no second
        # operation with the optional parameters filled in.
        self.assertEqual(len(data), 1)

        _spec, api_resource_name, _resource, operation_name, operation, _parameters = (
            data[0]
        )

        self.assertEqual(api_resource_name, "pets")
        self.assertEqual(operation_name, "findPets")
        self.assertEqual(operation.consumes, ["application/json"])
        self.assertEqual(operation.produces, ["application/json"])
        self.assertEqual(operation.path_name, "/pets")

        # Now we check the parameters for the operation
        self.assertEqual(len(operation.params), 1)

        param = operation.params.get("X-Foo-Header")
        self.assertEqual(param.param_spec["required"], True)
        self.assertEqual(param.param_spec["in"], "header")
        self.assertEqual(param.param_spec["type"], "string")
        self.assertEqual(param.fill, "56")

    def test_array_string_items_param_in_qs(self):
        specification_as_string = ArrayStringItemsQueryString().get_specification()
        http_response = self.generate_response(specification_as_string)
        handler = SpecificationHandler(http_response)

        data = [d for d in handler.get_api_information()]

        # The specification says that this query string parameter is
        # required and there is only one parameter, so there is no second
        # operation with the optional parameters filled in.
        self.assertEqual(len(data), 1)

        _spec, api_resource_name, _resource, operation_name, operation, _parameters = (
            data[0]
        )

        self.assertEqual(api_resource_name, "pets")
        self.assertEqual(operation_name, "addTags")
        self.assertEqual(operation.consumes, ["application/json"])
        self.assertEqual(operation.produces, ["application/json"])
        self.assertEqual(operation.path_name, "/pets")

        # Now we check the parameters for the operation
        self.assertEqual(len(operation.params), 1)

        param = operation.params.get("tags")
        self.assertEqual(param.param_spec["required"], True)
        self.assertEqual(param.param_spec["in"], "query")
        self.assertEqual(param.param_spec["type"], "array")
        self.assertEqual(param.fill, ["56"])

    def test_array_int_items_param_in_qs(self):
        specification_as_string = ArrayIntItemsQueryString().get_specification()
        http_response = self.generate_response(specification_as_string)
        handler = SpecificationHandler(http_response)

        data = [d for d in handler.get_api_information()]

        # The specification says that this query string parameter is
        # required and there is only one parameter, so there is no second
        # operation with the optional parameters filled in.
        self.assertEqual(len(data), 1)

        _spec, api_resource_name, _resource, operation_name, operation, _parameters = (
            data[0]
        )

        self.assertEqual(api_resource_name, "pets")
        self.assertEqual(operation_name, "addTags")
        self.assertEqual(operation.consumes, ["application/json"])
        self.assertEqual(operation.produces, ["application/json"])
        self.assertEqual(operation.path_name, "/pets")

        # Now we check the parameters for the operation
        self.assertEqual(len(operation.params), 1)

        param = operation.params.get("tags")
        self.assertEqual(param.param_spec["required"], True)
        self.assertEqual(param.param_spec["in"], "query")
        self.assertEqual(param.param_spec["type"], "array")
        self.assertEqual(param.fill, [42])

    def test_model_with_int_param_json(self):
        specification_as_string = IntParamJson().get_specification()
        http_response = self.generate_response(specification_as_string)
        handler = SpecificationHandler(http_response)

        data = [d for d in handler.get_api_information()]

        # The specification says that this query string parameter is
        # required and there is only one parameter, so there is no second
        # operation with the optional parameters filled in.
        self.assertEqual(len(data), 1)

        _spec, api_resource_name, _resource, operation_name, operation, _parameters = (
            data[0]
        )

        self.assertEqual(api_resource_name, "pets")
        self.assertEqual(operation_name, "addPet")
        self.assertEqual(operation.consumes, ["application/json"])
        self.assertEqual(operation.produces, ["application/json"])
        self.assertEqual(operation.path_name, "/pets")

        # Now we check the parameters for the operation
        self.assertEqual(len(operation.params), 1)

        param = operation.params.get("pet")
        self.assertEqual(param.param_spec["required"], True)
        self.assertEqual(param.param_spec["in"], "body")
        self.assertIn("schema", param.param_spec)
        self.assertEqual(param.fill, {"count": 42})

    def test_model_with_string_param_json(self):
        specification_as_string = StringParamJson().get_specification()
        http_response = self.generate_response(specification_as_string)
        handler = SpecificationHandler(http_response)

        data = [d for d in handler.get_api_information()]

        # The specification says that this query string parameter is
        # required and there is only one parameter, so there is no second
        # operation with the optional parameters filled in.
        self.assertEqual(len(data), 1)

        _spec, api_resource_name, _resource, operation_name, operation, _parameters = (
            data[0]
        )

        self.assertEqual(api_resource_name, "pets")
        self.assertEqual(operation_name, "addPet")
        self.assertEqual(operation.consumes, ["application/json"])
        self.assertEqual(operation.produces, ["application/json"])
        self.assertEqual(operation.path_name, "/pets")

        # Now we check the parameters for the operation
        self.assertEqual(len(operation.params), 1)

        param = operation.params.get("pet")
        self.assertEqual(param.param_spec["required"], True)
        self.assertEqual(param.param_spec["in"], "body")
        self.assertIn("schema", param.param_spec)
        self.assertEqual(param.fill, {"tag": "7", "name": "John"})

    def test_no_model_json_object_with_int_param_in_body(self):
        specification_as_string = IntParamNoModelJson().get_specification()
        http_response = self.generate_response(specification_as_string)
        handler = SpecificationHandler(http_response)

        data = [d for d in handler.get_api_information()]

        # The specification says that this query string parameter is
        # required and there is only one parameter, so there is no second
        # operation with the optional parameters filled in.
        self.assertEqual(len(data), 1)

        _spec, api_resource_name, _resource, operation_name, operation, _parameters = (
            data[0]
        )

        self.assertEqual(api_resource_name, "pets")
        self.assertEqual(operation_name, "addPet")
        self.assertEqual(operation.consumes, ["application/json"])
        self.assertEqual(operation.produces, ["application/json"])
        self.assertEqual(operation.path_name, "/pets")

        # Now we check the parameters for the operation
        self.assertEqual(len(operation.params), 1)

        param = operation.params.get("pet")
        self.assertEqual(param.param_spec["required"], True)
        self.assertEqual(param.param_spec["in"], "body")
        self.assertIn("schema", param.param_spec)
        self.assertEqual(param.fill, {"age": 42, "name": "John"})

    def test_no_model_json_object_complex_nested_in_body(self):
        specification_as_string = ComplexDereferencedNestedModel().get_specification()
        http_response = self.generate_response(specification_as_string)
        handler = SpecificationHandler(http_response)

        data = [d for d in handler.get_api_information()]

        # The specification says that this query string parameter is
        # required and there is only one parameter, so there is no second
        # operation with the optional parameters filled in.
        self.assertEqual(len(data), 1)

        _spec, api_resource_name, _resource, operation_name, operation, _parameters = (
            data[0]
        )

        self.assertEqual(api_resource_name, "pets")
        self.assertEqual(operation_name, "post_pets")
        self.assertEqual(operation.consumes, ["application/json"])
        self.assertEqual(operation.produces, ["application/json"])
        self.assertEqual(operation.path_name, "/pets")

        # Now we check the parameters for the operation
        self.assertEqual(len(operation.params), 1)

        param = operation.params.get("pet")
        self.assertEqual(param.param_spec["required"], True)
        self.assertEqual(param.param_spec["in"], "body")
        self.assertIn("schema", param.param_spec)

        expected_pet = {
            "birthdate": datetime.date(2017, 6, 30),
            "name": "John",
            "owner": {
                "address": {
                    "city": "Buenos Aires",
                    "postalCode": "90210",
                    "state": "AK",
                    "street1": "Bonsai Street 123",
                    "street2": "Bonsai Street 123",
                },
                "name": {"first": "56", "last": "Smith"},
            },
            "type": "cat",
        }
        self.assertEqual(param.fill, expected_pet)

    def test_array_with_model_items_param_in_json(self):
        specification_as_string = ArrayModelItems().get_specification()
        http_response = self.generate_response(specification_as_string)
        handler = SpecificationHandler(http_response)

        data = [d for d in handler.get_api_information()]

        # The specification says that this query string parameter is
        # required and there is only one parameter, so there is no second
        # operation with the optional parameters filled in.
        self.assertEqual(len(data), 1)

        _spec, api_resource_name, _resource, operation_name, operation, _parameters = (
            data[0]
        )

        self.assertEqual(api_resource_name, "pets")
        self.assertEqual(operation_name, "addMultiplePets")
        self.assertEqual(operation.consumes, ["application/json"])
        self.assertEqual(operation.produces, ["application/json"])
        self.assertEqual(operation.path_name, "/pets")

        # Now we check the parameters for the operation
        self.assertEqual(len(operation.params), 1)

        param = operation.params.get("pets")
        self.assertEqual(param.param_spec["required"], True)
        self.assertEqual(param.param_spec["in"], "body")
        self.assertIn("schema", param.param_spec)

        expected_value = [{"name": "John", "tag": "7"}]
        self.assertEqual(param.fill, expected_value)

    def test_model_param_nested_allOf_in_json(self):
        specification_as_string = NestedModel().get_specification()
        http_response = self.generate_response(specification_as_string)
        handler = SpecificationHandler(http_response)

        data = [d for d in handler.get_api_information()]

        self.assertEqual(len(data), 1)

        #
        # Assertions on call #1
        #
        _spec, api_resource_name, _resource, operation_name, operation, _parameters = (
            data[0]
        )

        self.assertEqual(api_resource_name, "pets")
        self.assertEqual(operation_name, "findPets")
        self.assertEqual(operation.consumes, ["application/json"])
        self.assertEqual(
            operation.produces,
            ["application/json", "application/xml", "text/xml", "text/html"],
        )
        self.assertEqual(operation.path_name, "/pets")

        # Now we check the parameters for the operation
        self.assertEqual(len(operation.params), 1)

        param = operation.params.get("pet")
        self.assertEqual(param.param_spec["required"], True)
        self.assertEqual(param.param_spec["in"], "body")
        self.assertIn("schema", param.param_spec)

        expected_value = {"tag": "7", "name": "John", "id": 42}
        self.assertEqual(param.fill, expected_value)

    def test_model_param_nested_loop_in_json(self):
        specification_as_string = NestedLoopModel().get_specification()
        http_response = self.generate_response(specification_as_string)
        handler = SpecificationHandler(http_response)

        data = [d for d in handler.get_api_information()]

        self.assertEqual(len(data), 1, data)

        #
        # Assertions on call #1
        #
        _spec, api_resource_name, _resource, operation_name, operation, _parameters = (
            data[0]
        )

        self.assertEqual(api_resource_name, "pets")
        self.assertEqual(operation_name, "findPets")
        self.assertEqual(operation.consumes, ["application/json"])
        self.assertEqual(
            operation.produces,
            ["application/json", "application/xml", "text/xml", "text/html"],
        )
        self.assertEqual(operation.path_name, "/pets")

    def test_dereferenced_pet_store(self):
        # See: dereferenced_pet_store.json , which was generated using
        # http://bigstickcarpet.com/swagger-parser/www/index.html#

        specification_as_string = DereferencedPetStore().get_specification()
        http_response = self.generate_response(specification_as_string)
        handler = SpecificationHandler(http_response)

        data = [d for d in handler.get_api_information()]
        self.assertEqual(len(data), 3)

        #
        # Assertions on call #1
        #
        _, api_resource_name, _, operation_name, operation, _ = next(
            item for item in data if item[3] == "get_pets_name"
        )

        self.assertEqual(api_resource_name, "pets")
        self.assertEqual(operation_name, "get_pets_name")
        self.assertEqual(operation.consumes, ["application/json"])
        self.assertEqual(operation.produces, ["application/json"])
        self.assertEqual(operation.path_name, "/pets/{name}")

        # Now we check the parameters for the operation
        self.assertEqual(len(operation.params), 1)

        param = operation.params.get("name")
        self.assertEqual(param.param_spec["required"], True)
        self.assertEqual(param.param_spec["in"], "path")
        self.assertEqual(param.param_spec["type"], "string")

        expected_value = "John"
        self.assertEqual(param.fill, expected_value)

        #
        # Assertions on call #2
        #
        _, api_resource_name, _, operation_name, operation, _ = next(
            item for item in data if item[3] == "get_pets"
        )

        self.assertEqual(api_resource_name, "pets")
        self.assertEqual(operation_name, "get_pets")
        self.assertEqual(operation.consumes, ["application/json"])
        self.assertEqual(operation.produces, ["application/json"])
        self.assertEqual(operation.path_name, "/pets")

        # Now we check the parameters for the operation
        self.assertEqual(len(operation.params), 0)

        #
        # Assertions on call #3
        #

        _spec, api_resource_name, _resource, operation_name, operation, _parameters = (
            next(item for item in data if item[3] == "post_pets")
        )

        self.assertEqual(api_resource_name, "pets")
        self.assertEqual(operation_name, "post_pets")
        self.assertEqual(operation.consumes, ["application/json"])
        self.assertEqual(operation.produces, ["application/json"])
        self.assertEqual(operation.path_name, "/pets")

        # Now we check the parameters for the operation
        self.assertEqual(len(operation.params), 1)

        param = operation.params.get("pet")
        self.assertEqual(param.param_spec["required"], True)
        self.assertEqual(param.param_spec["in"], "body")
        self.assertIn("schema", param.param_spec)

        expected_pet = {
            "owner": {
                "name": {"last": "Smith", "first": "56"},
                "address": {
                    "postalCode": "90210",
                    "street1": "Bonsai Street 123",
                    "street2": "Bonsai Street 123",
                    "state": "AK",
                    "city": "Buenos Aires",
                },
            },
            "type": "cat",
            "name": "John",
            "birthdate": datetime.date(2017, 6, 30),
        }
        self.assertEqual(param.fill, expected_pet)

    def test_parameter_handler_no_params(self):
        specification_as_string = NoParams().get_specification()
        http_response = self.generate_response(specification_as_string)
        handler = SpecificationHandler(http_response)
        self.check_parameter_setting(handler)

    def test_parameter_handler_simple_int_param_in_qs(self):
        specification_as_string = IntParamQueryString().get_specification()
        http_response = self.generate_response(specification_as_string)
        handler = SpecificationHandler(http_response)
        self.check_parameter_setting(handler)

    def test_parameter_handler_array_string_items_param_in_qs(self):
        specification_as_string = ArrayStringItemsQueryString().get_specification()
        http_response = self.generate_response(specification_as_string)
        handler = SpecificationHandler(http_response)
        self.check_parameter_setting(handler)

    def test_parameter_handler_no_model_json_object_complex_nested_in_body(self):
        specification_as_string = ComplexDereferencedNestedModel().get_specification()
        http_response = self.generate_response(specification_as_string)
        handler = SpecificationHandler(http_response)
        self.check_parameter_setting(handler)

    def test_parameter_handler_model_param_nested_allOf_in_json(self):
        specification_as_string = NestedModel().get_specification()
        http_response = self.generate_response(specification_as_string)
        handler = SpecificationHandler(http_response)
        self.check_parameter_setting(handler)

    def test_parameter_handler_multiple_paths_and_headers(self):
        specification_as_string = MultiplePathsAndHeaders().get_specification()
        http_response = self.generate_response(specification_as_string)
        handler = SpecificationHandler(http_response)
        self.check_parameter_setting(handler)

    def check_parameter_setting(self, spec_handler):
        data = [d for d in spec_handler.get_api_information()]
        self.assertIsNotNone(data)
        self.assertIsNotNone(spec_handler.spec)

        for api_resource_name, resource in list(spec_handler.spec.resources.items()):
            for operation_name, operation in list(resource.operations.items()):

                # Make sure that the parameter doesn't have a value yet
                for parameter in operation.params.values():
                    self.assertFalse(hasattr(parameter, "fill"))

                parameter_handler = ParameterHandler(spec_handler.spec, operation)
                updated_operation = parameter_handler.set_operation_params(True)
                self.assertOperation(operation, updated_operation)

                parameter_handler = ParameterHandler(spec_handler.spec, operation)
                updated_operation = parameter_handler.set_operation_params(False)
                self.assertOperation(operation, updated_operation)

    def assertOperation(self, operation, updated_operation):

        # Make sure that the parameter now has a value
        for parameter in updated_operation.params.values():
            self.assertTrue(hasattr(parameter, "fill"))

        # Make sure that the original operation doesn't get updated
        # after set_operation_params() call
        self.assertNotEqual(operation, updated_operation)


class TestSpecificationLoading(unittest.TestCase):

    @staticmethod
    def handler_for(body):
        return SpecificationHandler(TestSpecification.generate_response(body))

    def test_invalid_yaml_is_reported(self):
        handler = self.handler_for("swagger: [unclosed")

        self.assertEqual(list(handler.get_api_information()), [])
        self.assertEqual(len(handler.get_parsing_errors()), 1)
        self.assertIn("not in JSON or YAML format", handler.get_parsing_errors()[0])

    def test_yaml_python_tags_are_not_executed(self):
        marker = os.path.join(tempfile.mkdtemp(), "created-by-yaml")
        self.addCleanup(os.rmdir, os.path.dirname(marker))

        body = f"swagger: '2.0'\npaths: !!python/object/apply:os.mkdir ['{marker}']\n"
        handler = self.handler_for(body)

        self.assertEqual(list(handler.get_api_information()), [])
        self.assertFalse(os.path.exists(marker))
        self.assertEqual(len(handler.get_parsing_errors()), 1)

    def test_missing_version_information_is_added(self):
        handler = self.handler_for("info:\n  title: no versions\npaths: {}\n")

        self.assertEqual(list(handler.get_api_information()), [])
        self.assertEqual(handler.spec.spec_dict["swagger"], "2.0")
        self.assertEqual(handler.spec.spec_dict["info"]["version"], "1.0.0")
        self.assertEqual(handler.get_parsing_errors(), [])
