"""
construct_request.py

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

from bravado_core.exception import SwaggerMappingError
from bravado_core.param import marshal_param


def construct_request(operation, **op_kwargs):
    """
    Construct the outgoing request dict.

    :type operation: :class:`bravado_core.operation.Operation`
    :param op_kwargs: parameter name/value pairs to passed to the invocation of the operation.

    :return: request in dict form
    """
    url = operation.swagger_spec.api_url.rstrip("/") + operation.path_name

    request = {
        "method": str(operation.http_method.upper()),
        "url": url,
        "params": {},  # filled in downstream
        "headers": {},
    }

    construct_params(operation, request, op_kwargs)

    return request


def construct_params(operation, request, op_kwargs):
    """
    Given the parameters passed to the operation invocation, validates and
    marshals the parameters into the provided request dict.

    :type operation: :class:`bravado_core.operation.Operation`
    :type request: dict
    :param op_kwargs: the kwargs passed to the operation invocation

    :raises: SwaggerMappingError on extra parameters or when a required
             parameter is not supplied.
    """
    current_params = operation.params.copy()
    for param_name, param_value in op_kwargs.items():
        param = current_params.pop(param_name, None)
        if param is None:
            raise SwaggerMappingError(
                f"{operation.operation_id} does not have parameter {param_name}"
            )
        marshal_param(param, param_value, request)

    # Check required params and non-required params with a 'default' value
    for remaining_param in current_params.values():
        if remaining_param.required:
            raise SwaggerMappingError(f"{remaining_param.name} is a required parameter")
        if remaining_param.has_default():
            marshal_param(remaining_param, None, request)
