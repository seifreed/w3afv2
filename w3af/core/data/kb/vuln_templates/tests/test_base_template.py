"""
test_base_template.py

Copyright 2012 Andres Riancho

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

from w3af.core.data.fuzzer.mutants.postdata_mutant import PostDataMutant
from w3af.core.data.fuzzer.mutants.querystring_mutant import QSMutant
from w3af.core.data.kb.knowledge_base import kb
from w3af.core.data.kb.vuln_templates.base_template import BaseTemplate
from w3af.core.data.kb.vuln_templates.eval_template import EvalTemplate


class FailingTemplate(EvalTemplate):
    """A template whose vulnerability creation fails with `error`."""

    def __init__(self, error):
        super().__init__()
        self.error = error

    def create_vuln(self):
        raise self.error


def configure(template, **values):
    """
    Configure the template through its options, like a user would do from
    the console. Options not present in `values` get sensible defaults.
    """
    values = {
        "name": "SQL injection",
        "url": "http://host.tld/foo.php",
        "data": "id=3",
        "method": "GET",
        "vulnerable_parameter": "id",
        **values,
    }

    options = template.get_options()
    for name, value in values.items():
        options[name].set_value(value)
    template.set_options(options)
    return template


class BaseTemplateTest(unittest.TestCase):
    def setUp(self):
        kb.cleanup()
        self.addCleanup(kb.cleanup)

    def test_vuln_ids_are_consecutive(self):
        template = configure(EvalTemplate())

        one = template.get_vuln_id()
        two = template.get_vuln_id()

        self.assertEqual(one + 1, two)

    def test_abstract_methods(self):
        template = BaseTemplate()

        self.assertRaises(NotImplementedError, template.get_kb_location)
        self.assertRaises(NotImplementedError, template.get_vulnerability_name)

    def test_get_creates_query_string_vulnerability(self):
        vuln = configure(EvalTemplate()).create_vuln()

        self.assertIsInstance(vuln.get_mutant(), QSMutant)
        self.assertEqual(vuln.get_token_name(), "id")
        self.assertEqual(vuln.get_url().url_string, "http://host.tld/foo.php")
        self.assertEqual(vuln.get_name(), "SQL injection")
        self.assertIn('"Eval() code execution"', vuln.get_desc())

    def test_post_creates_post_data_vulnerability(self):
        vuln = configure(EvalTemplate(), method="POST").create_vuln()

        self.assertIsInstance(vuln.get_mutant(), PostDataMutant)
        self.assertEqual(vuln.get_method(), "POST")

    def test_store_in_kb(self):
        template = configure(EvalTemplate())

        template.store_in_kb()

        (stored,) = kb.get(*template.get_kb_location())
        self.assertEqual(stored.get_token_name(), "id")

    def test_requires_data(self):
        self.assertRaises(ValueError, configure, EvalTemplate(), data="")

    def test_requires_a_configured_vulnerable_parameter(self):
        with self.assertRaises(ValueError) as context:
            configure(EvalTemplate(), vulnerable_parameter="name")

        self.assertIn("one of the following values: id.", str(context.exception))

    def test_vuln_creation_errors_become_value_errors(self):
        with self.assertRaises(ValueError) as context:
            configure(FailingTemplate(RuntimeError("Invalid token")))
        self.assertEqual(str(context.exception), "Invalid token")

        with self.assertRaises(ValueError) as context:
            configure(FailingTemplate(KeyError("id")))
        self.assertEqual(
            str(context.exception), "The vulnerable parameter \"'id'\" was not found"
        )
