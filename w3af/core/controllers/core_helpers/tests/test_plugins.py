# -*- coding: UTF-8 -*-
"""
test_plugins.py

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

import itertools
import unittest

import pytest

import w3af.core.controllers.output_manager as om
from w3af.core.controllers.core_helpers.plugins import CorePlugins
from w3af.core.controllers.w3af_core import w3afCore
from w3af.core.exceptions import BaseFrameworkException


class TestPluginRegistryStructure(unittest.TestCase):

    def test_registries_follow_plugin_package_types(self):
        core_plugins = CorePlugins(None, om.out, om.manager)
        plugin_types = set(core_plugins.get_plugin_types())

        self.assertEqual(set(core_plugins.plugins), plugin_types)
        self.assertEqual(set(core_plugins.get_all_enabled_plugins()), plugin_types)
        self.assertEqual(
            set(core_plugins.get_all_plugin_options()), plugin_types | {"attack"}
        )

    def test_plugin_types_omit_cache_directories(self):
        plugin_types = CorePlugins(None, om.out, om.manager).get_plugin_types()

        self.assertNotIn("__pycache__", plugin_types)


@pytest.mark.smoke
class TestW3afCorePlugins(unittest.TestCase):

    def setUp(self):
        super().setUp()

        self.core = w3afCore()
        self.addCleanup(self.core.worker_pool.terminate_join)

    def test_get_plugin_types(self):
        plugin_types = self.core.plugins.get_plugin_types()
        expected = {
            "grep",
            "output",
            "mangle",
            "audit",
            "crawl",
            "evasion",
            "bruteforce",
            "auth",
            "infrastructure",
        }
        self.assertEqual(set(plugin_types), expected)
        self.assertEqual(plugin_types, sorted(plugin_types))

    def test_get_plugin_list_audit(self):
        plugin_list = self.core.plugins.get_plugin_list("audit")

        expected = {"sqli", "xss", "eval"}
        self.assertTrue(set(plugin_list).issuperset(expected))

    def test_get_plugin_list_crawl(self):
        plugin_list = self.core.plugins.get_plugin_list("crawl")

        expected = {"web_spider", "spider_man"}
        self.assertTrue(set(plugin_list).issuperset(expected))

    def test_get_plugin_inst(self):
        plugin_inst = self.core.plugins.get_plugin_inst("audit", "sqli")

        self.assertEqual(plugin_inst.get_name(), "sqli")

    def test_get_plugin_inst_all(self):
        for plugin_type in itertools.chain(
            self.core.plugins.get_plugin_types(), ["attack"]
        ):
            for plugin_name in self.core.plugins.get_plugin_list(plugin_type):
                plugin_inst = self.core.plugins.get_plugin_inst(
                    plugin_type, plugin_name
                )
                self.assertEqual(plugin_inst.get_name(), plugin_name)

    def test_set_plugins(self):
        enabled = [
            "sqli",
        ]
        self.core.plugins.set_plugins(enabled, "audit")
        retrieved = self.core.plugins.get_enabled_plugins("audit")
        self.assertEqual(enabled, retrieved)

    def test_set_plugins_negative(self):
        enabled = [
            "fake",
        ]
        self.assertRaises(ValueError, self.core.plugins.set_plugins, enabled, "output")

    def test_set_plugins_negative_without_raise(self):
        enabled = [
            "fake",
        ]
        unknown_plugins = self.core.plugins.set_plugins(
            enabled, "output", raise_on_error=False
        )
        self.assertEqual(enabled, unknown_plugins)
        self.core.plugins.init_plugins()

    def test_get_all_enabled_plugins(self):
        enabled_audit = ["sqli", "xss"]
        enabled_grep = ["private_ip"]
        self.core.plugins.set_plugins(enabled_audit, "audit")
        self.core.plugins.set_plugins(enabled_grep, "grep")

        all_enabled = self.core.plugins.get_all_enabled_plugins()

        self.assertEqual(enabled_audit, all_enabled["audit"])
        self.assertEqual(enabled_grep, all_enabled["grep"])

    def test_plugin_options(self):
        plugin_inst = self.core.plugins.get_plugin_inst("crawl", "web_spider")
        options_1 = plugin_inst.get_options()

        self.core.plugins.set_plugin_options("crawl", "web_spider", options_1)
        options_2 = self.core.plugins.get_plugin_options("crawl", "web_spider")

        self.assertEqual(options_1, options_2)

    def test_output_plugin_options_reach_the_output_manager(self):
        previous_output_plugins = list(om.manager.get_output_plugins())
        default_options = self.core.plugins.get_plugin_inst(
            "output", "console"
        ).get_options()
        self.addCleanup(om.manager.set_output_plugins, previous_output_plugins)
        self.addCleanup(om.manager.set_plugin_options, "console", default_options)

        options = self.core.plugins.get_plugin_inst("output", "console").get_options()
        options["use_colors"].set_value(not options["use_colors"].get_value())
        self.core.plugins.set_plugin_options("output", "console", options)

        om.manager.set_output_plugins(["console"])

        console = om.manager.get_output_plugin_inst()[0]
        self.assertEqual(
            console.get_options()["use_colors"].get_value(),
            options["use_colors"].get_value(),
        )

    def test_get_plugin_type_desc(self):
        description = self.core.plugins.get_plugin_type_desc("audit")

        self.assertIn("vulnerabilities", description)

    def test_get_plugin_type_desc_unknown_type(self):
        with self.assertRaisesRegex(BaseFrameworkException, "Unknown plugin type"):
            self.core.plugins.get_plugin_type_desc("unknown_type")

    def test_init_plugins_twice_applies_latest_options(self):
        self.core.plugins.set_plugins(["web_spider"], "crawl")
        self.core.plugins.init_plugins()

        options = self.core.plugins.get_plugin_inst("crawl", "web_spider").get_options()
        options["only_forward"].set_value(True)
        self.core.plugins.set_plugin_options("crawl", "web_spider", options)
        self.core.plugins.init_plugins()

        crawl_plugins = self.core.plugins.plugins["crawl"]
        self.assertEqual(len(crawl_plugins), 1)
        self.assertTrue(crawl_plugins[0].get_options()["only_forward"].get_value())

    def test_plugin_options_invalid(self):
        self.assertRaises(
            TypeError, self.core.plugins.set_plugin_options, "crawl", "web_spider", None
        )

    def test_plugin_options_partially_invalid_scan_does_not_start(self):
        self.core.plugins.set_plugins(["generic"], "auth")

        plugin_inst = self.core.plugins.get_plugin_inst("auth", "generic")
        options = plugin_inst.get_options()

        username = options["username"]
        username.set_value("andres")

        password = options["password"]
        password.set_value("foobar")

        # There are missing configuration parameters, so it's ok for this to
        # fail
        self.assertRaises(
            BaseFrameworkException,
            self.core.plugins.set_plugin_options,
            "auth",
            "generic",
            options,
        )

        # Do not start the scan if the user failed to configure the plugins
        # https://github.com/andresriancho/w3af/issues/7477
        self.assertRaises(BaseFrameworkException, self.core.plugins.init_plugins)

        # Now we set all the options again and it should succeed
        options["username_field"].set_value("username")
        options["password_field"].set_value("password")
        options["auth_url"].set_value("http://login.com/")
        options["check_url"].set_value("http://check.com/")
        options["check_string"].set_value("abc")

        self.core.plugins.set_plugin_options("auth", "generic", options)
        self.core.plugins.init_plugins()

    def test_init_plugins(self):
        enabled = ["web_spider"]
        self.core.plugins.set_plugins(enabled, "crawl")
        self.core.plugins.init_plugins()

        self.assertEqual(
            len(self.core.plugins.plugins["crawl"]),
            1,
            self.core.plugins.plugins["crawl"],
        )

        plugin_inst = next(iter(self.core.plugins.plugins["crawl"]))
        self.assertEqual(plugin_inst.get_name(), "web_spider")

    def test_enable_all(self):
        enabled = ["all"]
        self.core.plugins.set_plugins(enabled, "crawl")
        self.core.plugins.init_plugins()

        self.assertEqual(
            self.core.plugins.get_enabled_plugins("crawl"),
            self.core.plugins.get_plugin_list("crawl"),
        )
        self.assertEqual(
            set(self.core.plugins.get_enabled_plugins("crawl")),
            set(self.core.plugins.get_plugin_list("crawl")),
        )

        self.assertEqual(
            len(set(self.core.plugins.get_enabled_plugins("crawl"))),
            len(set(self.core.plugins.get_plugin_list("crawl"))),
        )

    def test_exclusion_without_all_disables_the_plugin(self):
        self.core.plugins.set_plugins(["!web_spider"], "crawl")
        self.core.plugins.init_plugins()

        self.assertEqual(self.core.plugins.get_enabled_plugins("crawl"), [])

    def test_enable_all_but_web_spider(self):
        enabled = ["all", "!web_spider"]
        self.core.plugins.set_plugins(enabled, "crawl")
        self.core.plugins.init_plugins()

        all_plugins = self.core.plugins.get_plugin_list("crawl")
        all_plugins = all_plugins[:]
        all_plugins.remove("web_spider")

        self.assertEqual(
            set(self.core.plugins.get_enabled_plugins("crawl")), set(all_plugins)
        )

    def test_enable_all_but_two(self):
        enabled = ["all", "!web_spider", "!archive_dot_org"]
        self.core.plugins.set_plugins(enabled, "crawl")
        self.core.plugins.init_plugins()

        all_plugins = self.core.plugins.get_plugin_list("crawl")
        all_plugins = all_plugins[:]
        all_plugins.remove("web_spider")
        all_plugins.remove("archive_dot_org")

        self.assertEqual(
            set(self.core.plugins.get_enabled_plugins("crawl")), set(all_plugins)
        )

    def test_enable_not_web_spider_all(self):
        enabled = ["!web_spider", "all"]
        self.core.plugins.set_plugins(enabled, "crawl")
        self.core.plugins.init_plugins()

        all_plugins = self.core.plugins.get_plugin_list("crawl")
        all_plugins = all_plugins[:]
        all_plugins.remove("web_spider")

        self.assertEqual(
            set(self.core.plugins.get_enabled_plugins("crawl")), set(all_plugins)
        )

    def test_enable_dependency_same_type(self):
        enabled_infra = [
            "php_eggs",
        ]
        self.core.plugins.set_plugins(enabled_infra, "infrastructure")
        self.core.plugins.init_plugins()

        enabled_infra.append("server_header")

        self.assertEqual(
            set(self.core.plugins.get_enabled_plugins("infrastructure")),
            set(enabled_infra),
        )

    def test_enable_dependency_same_type_order(self):
        enabled_infra = [
            "php_eggs",
        ]
        self.core.plugins.set_plugins(enabled_infra, "infrastructure")
        self.core.plugins.init_plugins()

        self.assertEqual(
            self.core.plugins.get_enabled_plugins("infrastructure").index(
                "server_header"
            ),
            0,
        )
        self.assertEqual(
            self.core.plugins.get_enabled_plugins("infrastructure").index("php_eggs"), 1
        )

        self.assertEqual(
            self.core.plugins.plugins["infrastructure"][0].get_name(), "server_header"
        )
        self.assertEqual(
            self.core.plugins.plugins["infrastructure"][1].get_name(), "php_eggs"
        )

    def test_enable_dependency_different_type(self):
        enabled_crawl = [
            "url_fuzzer",
        ]
        self.core.plugins.set_plugins(enabled_crawl, "crawl")

        enabled_infra = [
            "allowed_methods",
        ]

        self.core.plugins.init_plugins()

        self.assertEqual(
            set(self.core.plugins.get_enabled_plugins("crawl")), set(enabled_crawl)
        )

        self.assertEqual(
            set(self.core.plugins.get_enabled_plugins("infrastructure")),
            set(enabled_infra),
        )

    def test_enable_all_all(self):
        for plugin_type in self.core.plugins.get_plugin_types():
            self.core.plugins.set_plugins(
                [
                    "all",
                ],
                plugin_type,
            )

        self.core.plugins.init_plugins()

        for plugin_type in self.core.plugins.get_plugin_types():
            enabled_plugins = self.core.plugins.get_enabled_plugins(plugin_type)
            all_plugins = self.core.plugins.get_plugin_list(plugin_type)
            self.assertEqual(set(enabled_plugins), set(all_plugins))
            self.assertEqual(len(enabled_plugins), len(all_plugins))
