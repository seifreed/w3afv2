"""
test_completion.py

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

import w3af.core.controllers.output_manager as om
from w3af.core.ui.console.console_ui import ConsoleUI
from w3af.core.ui.console.root_menu import rootMenu
from w3af.core.ui.console.tests.helper import ConsoleTestHelper


def _values(completions):
    return [completion for _part, completion in completions]


class TestConsoleCompletion(ConsoleTestHelper):
    """
    Exercise the tab-completion (suggest/_para_*) logic of the console menus
    directly against a real w3afCore.
    """

    def setUp(self):
        super().setUp()
        self.console = ConsoleUI(do_upd=False)
        self.root = rootMenu("w3af", self.console, self.console._w3af)

    def tearDown(self):
        self.console._w3af.quit()
        super().tearDown()

    def _audit_menu(self):
        return self.root.get_children()["plugins"].get_children()["audit"]

    def _config_menu(self):
        return self.root.get_children()["misc-settings"]

    def test_root_suggests_commands_and_children(self):
        values = _values(self.root.suggest([], "pl"))
        self.assertTrue(any(value.startswith("plugins") for value in values))

    def test_root_delegates_to_child(self):
        completions = self.root.suggest(["plugins"], "")
        self.assertIsNotNone(completions)

    def test_root_suggest_unknown_child_returns_empty(self):
        self.assertEqual(self.root.suggest_commands("nope/leaf", True), [])

    def test_plugins_type_suggest_commands_and_params(self):
        audit = self._audit_menu()
        values = _values(audit.suggest_commands("xs"))
        self.assertIn("xss", values)

        param_values = _values(audit.suggest_params("config", [], ""))
        self.assertTrue(param_values)

        # Unknown command falls back to suggesting plugin names to enable
        self.assertIsInstance(audit.suggest_params("xss", [], ""), list)

    def test_plugins_type_para_desc_and_config(self):
        audit = self._audit_menu()
        self.assertTrue(_values(audit._para_desc([], "x")))
        self.assertEqual(audit._para_desc(["xss"], "x"), [])
        self.assertTrue(_values(audit._para_config([], "x")))
        self.assertEqual(audit._para_config(["xss"], "x"), [])
        self.assertEqual(audit._para_list(["enabled"], "x"), [])

    def test_config_para_set(self):
        config = self._config_menu()
        # No params: suggest option names
        self.assertTrue(_values(config._para_set([], "")))
        # Unknown option name
        self.assertEqual(config._para_set(["no_such_option"], ""), [])
        # Too many params
        self.assertEqual(config._para_set(["a", "b"], ""), [])

    def test_config_para_set_known_option(self):
        config = self._config_menu()
        option_name = next(iter(config._opt_dict))
        self.assertIsInstance(config._para_set([option_name], ""), list)

    def test_config_para_help_lists_options(self):
        config = self._config_menu()
        self.assertTrue(config._para_help([], ""))

    def test_config_help_for_option(self):
        config = self._config_menu()
        option_name = next(iter(config._opt_dict))
        config._cmd_help([option_name])
        om.manager.process_all_messages()
        self.assertTrue(self._mock_stdout.messages)

    def test_plugins_para_list(self):
        plugins = self.root.get_children()["plugins"]
        self.assertTrue(_values(plugins._para_list([], "")))
        self.assertTrue(_values(plugins._para_list(["audit"], "")))
        self.assertEqual(plugins._para_list(["audit", "enabled"], ""), [])
