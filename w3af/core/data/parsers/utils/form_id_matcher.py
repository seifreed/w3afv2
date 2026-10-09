"""
form_id_matcher.py

Copyright 2017 Andres Riancho

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
import re
from typing import ClassVar

FORM_ID_FORMAT_ERROR = """\
The provided form-id JSON is incorrect. Form ids must be JSON objects with the
following structure:

{"action":"/products/.*",
 "inputs": ["comment"],
 "attributes": {"class": "comments-form"},
 "hosted_at_url": "/products/.*"}

Any of the top level object attributes can be missing but no extra top level
attributes are allowed. Also, the types associated with each key needs to match
the example above.

Note that the values for "action" and "hosted_at_url" need to be valid regular
expressions.

Please read the documentation for more details and examples on how to configure
the form-id setting.
"""


class InvalidFormIDError(ValueError):
    """Raised when a user supplied form-id does not have the expected format."""

    def __init__(self, message=FORM_ID_FORMAT_ERROR):
        super().__init__(message)


def _is_optional_pattern(value):
    return value is None or isinstance(value, re.Pattern)


def _is_optional_str_list(value):
    if value is None:
        return True
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _is_optional_str_dict(value):
    if value is None:
        return True
    return isinstance(value, dict) and all(
        isinstance(k, str) and isinstance(v, str) for k, v in value.items()
    )


def _compile_optional_pattern(pattern):
    if pattern is None:
        return None
    try:
        return re.compile(pattern)
    except (re.error, TypeError) as error:
        raise InvalidFormIDError from error


class FormIDMatcher:
    """
    This class describes the form attributes that the user wants to match.

    In most cases this class is constructed from user-configured json object
    such as:

        {"action":"/products/.*",
         "inputs": ["comment"],
         "method": "get",
         "attributes": {"class": "comments-form"},
         "hosted_at_url": "/products/.*"}

    And then used in a call to FormID.match(...)

    :see: https://github.com/andresriancho/w3af/issues/15161
    """

    ALLOWED_ATTRS: ClassVar[frozenset[str]] = frozenset(
        ("action", "inputs", "attributes", "hosted_at_url", "method")
    )

    def __init__(
        self, action=None, inputs=None, attributes=None, hosted_at_url=None, method=None
    ):
        """
        :param action: Regular expression object matching URL where
                       the form is sent
        :param inputs: A list with the names of the form parameters
        :param attributes: The form tag attributes as seen in the HTML
        :param hosted_at_url: Regular expression object matching URL
                              where the form should
        :param method: The HTTP method used to submit the form
        """
        self.verify_data_types(action, inputs, attributes, hosted_at_url, method)

        self.action = action
        self.inputs = inputs
        self.attributes = attributes
        self.hosted_at_url = hosted_at_url
        self.method = method

    def verify_data_types(self, action, inputs, attributes, hosted_at_url, method):
        """
        Strict attribute type checking to make sure we get what we expect from
        all the callers

        :param action: URL where the form is sent
        :param inputs: A list with the names of the form parameters
        :param attributes: The form tag attributes as seen in the HTML
        :param hosted_at_url: The URL where the form appeared
        :return: True if all attributes match our requirements, otherwise an
                 exception is raised
        """
        valid = (
            _is_optional_pattern(action)
            and _is_optional_str_list(inputs)
            and _is_optional_str_dict(attributes)
            and _is_optional_pattern(hosted_at_url)
            and (method is None or isinstance(method, str))
        )
        if not valid:
            raise InvalidFormIDError

        return True

    def to_dict(self):
        """
        :return: This object as a dict which can be easily serialized as json
        """
        data = {}

        for unmodified in ["inputs", "attributes", "method"]:
            if self.__dict__[unmodified] is not None:
                data[unmodified] = self.__dict__[unmodified]

        if self.action is not None:
            data["action"] = self.action.pattern

        if self.hosted_at_url is not None:
            data["hosted_at_url"] = self.hosted_at_url.pattern

        return data

    @classmethod
    def from_json(cls, json_string):
        """
        This is a "constructor" for the FormID class.

        Users configure form-ids as JSON objects in the configuration, we need to
        parse this here to convert them to FormIDs

        :param json_string: A user provided string which should be in json format
        :return: A FormIDMatcher object
        """
        # For now we just let the exception generated by invalid json raise without
        # any handling
        json_data = json.loads(json_string)

        # Strict input checks are done in __init__ -> verify_data_types
        return cls.from_json_list_data(json_data)

    @classmethod
    def from_json_list_data(cls, json_list_item):
        """
        This is a "constructor" for the FormID class.

        Users configure form-ids as JSON objects in the configuration, we need to
        parse this here to convert them to FormIDs

        :param json_list_item: A user provided python object which we use to build
                               the FormIDMatcher
        :return: A FormIDMatcher object
        """
        # Check the root JSON object format
        if not isinstance(json_list_item, dict):
            raise InvalidFormIDError

        action = json_list_item.get("action", None)
        inputs = json_list_item.get("inputs", None)
        attributes = json_list_item.get("attributes", None)
        hosted_at_url = json_list_item.get("hosted_at_url", None)
        method = json_list_item.get("method", None)

        if not cls.ALLOWED_ATTRS.issuperset(json_list_item):
            raise InvalidFormIDError

        # User configured action and hosted_at_url must be valid regular expressions
        action = _compile_optional_pattern(action)
        hosted_at_url = _compile_optional_pattern(hosted_at_url)

        # Strict input checks are done in __init__ -> verify_data_types
        return cls(action, inputs, attributes, hosted_at_url, method)

    def __str__(self):
        return f"<FormIDMatcher: {self.__dict__}>"
