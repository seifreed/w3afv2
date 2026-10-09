"""
test_menus.py

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

from w3af.core.ui.console.console_ui import ConsoleUI
from w3af.core.ui.console.tests.helper import ConsoleTestHelper


class TestConsoleMenus(ConsoleTestHelper):
    """
    Drive the console menus through the real command interpreter, covering
    navigation, help, plugin listing/configuration, the knowledge-base menu
    and error handling, all without running a scan.
    """

    def _run(self, commands):
        self.console = ConsoleUI(commands=commands, do_upd=False)
        self.console.sh()
        return "".join(self._captured_stdout.messages)

    def test_help_and_keys_and_print(self):
        output = self._run(
            [
                "help",
                "keys",
                "help back",
                "help no_such_subject",
                "print w3af_core",
                "print this is not valid python",
                "exit",
            ]
        )
        self.assertIn("No help for 'no_such_subject'", output)
        self.assertIn("Unknown variable.", output)

    def test_unknown_command(self):
        output = self._run(["this_command_does_not_exist", "exit"])
        self.assertIn("Unknown command", output)

    def test_plugins_menu_listing_and_desc(self):
        output = self._run(
            [
                "plugins",
                "audit",
                "audit xss",
                "audit",
                "list audit enabled",
                "audit desc xss",
                "audit desc no_such_plugin",
                "audit desc",
                "output",
                "back",
                "exit",
            ]
        )
        self.assertIn("xss", output)
        self.assertIn("Unknown plugin: 'no_such_plugin'", output)

    def test_plugin_config_menu(self):
        output = self._run(
            [
                "plugins",
                "audit config xss",
                "view",
                "set",
                "set no_such_option value",
                "help",
                "help no_such_option",
                "back",
                "back",
                "exit",
            ]
        )
        self.assertIn("Invalid call to set", output)
        self.assertIn('Unknown option: "no_such_option".', output)

    def test_enable_unknown_plugin(self):
        output = self._run(["plugins", "audit no_such_plugin", "back", "exit"])
        self.assertIn("Unknown plugin: 'no_such_plugin'", output)

    def test_config_set_and_save_misc_settings(self):
        output = self._run(
            [
                "misc-settings",
                "view",
                "set msf_location /tmp/",
                "back",
                "misc-settings",
                "view",
                "back",
                "exit",
            ]
        )
        self.assertIn("The configuration has been saved.", output)
        self.assertIn("msf_location", output)

    def test_kb_menu(self):
        output = self._run(
            [
                "kb",
                "list",
                "list vulns",
                "list info",
                "list shells",
                "list no_such_type",
                "add",
                "add one two",
                "add no_such_template",
                "back",
                "exit",
            ]
        )
        self.assertIn("Type no_such_type is unknown", output)
        self.assertIn("Type no_such_template is unknown", output)

    def test_kb_add_template_missing_data(self):
        output = self._run(["kb", "add sqli", "view", "back", "back", "exit"])
        self.assertIn("This vulnerability requires data to be configured.", output)

    def test_kb_add_template_stored(self):
        output = self._run(
            [
                "kb",
                "add sqli",
                "set url http://host.tld/?id=1",
                "set data id=1",
                "set vulnerable_parameter id",
                "back",
                "back",
                "exit",
            ]
        )
        self.assertIn("knowledge base", output)

    def test_profiles_menu(self):
        output = self._run(
            [
                "profiles",
                "list",
                "list unexpected_param",
                "use",
                "back",
                "exit",
            ]
        )
        self.assertIn("No parameters expected", output)
        self.assertIn("Parameter missing", output)
