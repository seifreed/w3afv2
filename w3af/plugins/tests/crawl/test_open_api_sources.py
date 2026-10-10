"""
test_open_api_sources.py

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

import json
import os
import tempfile
import unittest
from typing import ClassVar

import yaml

import w3af.core.controllers.output_manager as om
import w3af.core.data.kb.knowledge_base as kb
from w3af.core.controllers.misc_settings import MiscSettings
from w3af.core.data.kb.config import Config
from w3af.core.data.parsers.doc.open_api.tests.example_specifications import (
    NestedModel,
    PetstoreSimpleModel,
)
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.request.fuzzable_request import FuzzableRequest
from w3af.plugins.crawl.open_api import open_api
from w3af.plugins.tests.helper import MockResponse, PluginConfig, PluginTest

INDEX_PAGE = [MockResponse("http://w3af.org/", "index")]


def api_urls(known_requests):
    return {fr.get_uri().url_string for fr in known_requests}


class SpecFileTest(PluginTest):
    """
    Base class for the tests which load the specification from a local file
    """

    target_url = "http://w3af.org/"

    MOCK_RESPONSES: ClassVar[list] = INDEX_PAGE

    def write_spec(self, file_name, content):
        spec_dir = tempfile.TemporaryDirectory()
        self.addCleanup(spec_dir.cleanup)

        spec_path = os.path.join(spec_dir.name, file_name)
        with open(spec_path, "w") as spec_fd:
            spec_fd.write(content)

        return spec_path

    def scan_with_spec_file(self, spec_path):
        plugins = {
            "crawl": (
                PluginConfig(
                    "open_api",
                    ("custom_spec_location", spec_path, PluginConfig.INPUT_FILE),
                ),
            )
        }
        self._scan(self.target_url, plugins)


class TestOpenAPICustomJsonSpec(SpecFileTest):

    def test_endpoints_are_loaded_from_local_json_file(self):
        spec_path = self.write_spec("spec.json", NestedModel().get_specification())

        self.scan_with_spec_file(spec_path)

        infos = self.kb.get("open_api", "open_api")
        self.assertEqual(
            [i.get_name() for i in infos],
            ["Open API specification found", "Open API missing credentials"],
        )
        self.assertIn(
            "http://w3af.org/api/pets",
            api_urls(self.kb.get_all_known_fuzzable_requests()),
        )

        requested = {r.uri for r in self.received_requests}
        self.assertNotIn("http://w3af.org/openapi.json", requested)
        self.assertNotIn("http://w3af.org/swagger.json", requested)


class TestOpenAPICustomYamlSpec(SpecFileTest):

    def test_endpoints_are_loaded_from_local_yaml_file(self):
        spec = yaml.safe_dump(json.loads(NestedModel().get_specification()))
        spec_path = self.write_spec("spec.yaml", spec)

        self.scan_with_spec_file(spec_path)

        self.assertIn(
            "http://w3af.org/api/pets",
            api_urls(self.kb.get_all_known_fuzzable_requests()),
        )


class TestOpenAPICustomSpecUnknownExtension(SpecFileTest):

    def test_file_with_unknown_extension_is_skipped(self):
        spec_path = self.write_spec("spec.txt", NestedModel().get_specification())

        self.scan_with_spec_file(spec_path)

        self.assertEqual(self.kb.get("open_api", "open_api"), [])
        self.assertNotIn(
            "http://w3af.org/api/pets",
            api_urls(self.kb.get_all_known_fuzzable_requests()),
        )


class TestOpenAPIYamlServedWithoutTextContentType(PluginTest):
    target_url = "http://w3af.org/"

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(
            "http://w3af.org/openapi.yaml",
            yaml.safe_dump(json.loads(NestedModel().get_specification())),
            content_type="application/x-yaml",
        )
    ]

    def test_binary_yaml_response_is_parsed(self):
        plugins = {"crawl": (PluginConfig("open_api"),)}
        self._scan(self.target_url, plugins)

        infos = self.kb.get("open_api", "open_api")
        self.assertEqual(infos[0].get_name(), "Open API specification found")
        self.assertIn(
            "http://w3af.org/api/pets",
            api_urls(self.kb.get_all_known_fuzzable_requests()),
        )


class TestOpenAPIOperationsOutsideTarget(PluginTest):
    target_url = "http://w3af.org/"

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(
            "http://w3af.org/openapi.json",
            PetstoreSimpleModel().get_specification(),
            content_type="application/json",
        )
    ]

    def test_operations_pointing_to_other_domains_are_ignored(self):
        plugins = {"crawl": (PluginConfig("open_api"),)}
        self._scan(self.target_url, plugins)

        infos = self.kb.get("open_api", "open_api")
        self.assertEqual(infos[0].get_name(), "Open API specification found")

        urls = api_urls(self.kb.get_all_known_fuzzable_requests())
        self.assertEqual(urls, {"http://w3af.org/", "http://w3af.org/openapi.json"})


class TestOpenAPIWithoutUrlPartsDiscovery(PluginTest):
    target_url = "http://w3af.org/"

    MOCK_RESPONSES: ClassVar[list] = [
        MockResponse(
            "http://w3af.org/openapi.json",
            NestedModel().get_specification(),
            content_type="application/json",
        )
    ]

    def test_api_calls_have_no_forced_url_parts(self):
        plugins = {
            "crawl": (
                PluginConfig(
                    "open_api",
                    ("discover_fuzzable_url_parts", False, PluginConfig.BOOL),
                ),
            )
        }
        self._scan(self.target_url, plugins)

        api_calls = [
            fr
            for fr in self.kb.get_all_known_fuzzable_requests()
            if fr.get_url().get_path() == "/api/pets"
        ]
        self.assertEqual(len(api_calls), 1)
        self.assertEqual(api_calls[0].get_force_fuzzing_url_parts(), [])


class TestOpenAPIPluginInternals(unittest.TestCase):

    def setUp(self):
        kb.kb.cleanup()
        self.addCleanup(kb.kb.cleanup)
        self.addCleanup(MiscSettings(cf).set_default_values)

        self.plugin = open_api()
        self.plugin.set_configuration(cf)
        self.addCleanup(self.plugin.end)

    def test_common_paths_are_generated_only_once(self):
        fuzzable_request = FuzzableRequest(URL("http://w3af.org/a/"))

        first = list(self.plugin._spec_url_generator_common(fuzzable_request))
        second = list(self.plugin._spec_url_generator_common(fuzzable_request))

        self.assertEqual(
            len(first), len(open_api.DIRECTORIES) * len(open_api.FILENAMES)
        )
        self.assertEqual(second, [])

    def test_file_name_fuzzing_is_enabled_without_url_parts_discovery(self):
        options = self.plugin.get_options()
        options["discover_fuzzable_url_parts"].set_value(False)
        self.plugin.set_options(options)

        self.plugin._enable_file_name_fuzzing()

        self.assertTrue(cf.get("fuzz_url_filenames"))
        self.assertTrue(cf.get("fuzz_url_parts"))

    def test_api_call_without_configured_targets_is_out_of_scope(self):
        previous_targets = cf.get("targets")
        self.addCleanup(cf.save, "targets", previous_targets)
        cf.save("targets", [])

        api_call = FuzzableRequest(URL("http://w3af.org/api/pets"))

        self.assertFalse(open_api._is_target_domain(api_call, om.out, cf))

    def test_long_description_mentions_supported_files(self):
        self.assertIn("openapi.yaml", self.plugin.get_long_desc())


cf = Config()
