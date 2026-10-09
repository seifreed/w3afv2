"""
test_profiles.py

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

import subprocess
import sys
import tempfile

import pytest

from w3af.core.controllers.core_helpers.tests.test_profiles import (
    assertProfileOptionsPreserved,
)
from w3af.core.controllers.exceptions import BaseFrameworkException
from w3af.core.data.db.startup_cfg import StartUpConfig
from w3af.core.data.profile.profile import profile
from w3af.core.filesystem import create_temp_dir, remove_temp_dir
from w3af.core.ui.console.console_ui import ConsoleUI
from w3af.core.ui.console.tests.helper import ConsoleTestHelper


@pytest.mark.smoke
class TestProfilesConsoleUI(ConsoleTestHelper):
    """
    Load profiles from the console UI.
    """

    def setUp(self):
        super().setUp()
        self._remove_if_exists(self.get_profile_name())

    def tearDown(self):
        super().tearDown()
        self._remove_if_exists(self.get_profile_name())

    def get_profile_name(self):
        profile_name = self.id()
        profile_name = profile_name.replace(".", "-")
        profile_name = profile_name.replace(":", "-")
        profile_name = profile_name.lower()
        return profile_name

    def _remove_if_exists(self, profile_name):
        try:
            profile_inst = profile(profile_name)
            profile_inst.remove()
        except BaseFrameworkException:
            pass

    def _assert_exists(self, profile_name):
        try:
            profile(profile_name)
        except BaseFrameworkException as error:
            pytest.fail(f"The {profile_name} profile does NOT exist: {error}")

    def _assert_equal(self, profile_name_a, profile_name_b):
        p1 = profile(profile_name_a, workdir=".")
        p2 = profile(profile_name_b, workdir=".")

        assertProfileOptionsPreserved(p1.profile_file_name, p2.profile_file_name)

    def test_load_profile_exists(self):
        commands_to_run = ["profiles", "help", "use OWASP_TOP10", "exit"]

        expected = (
            "The plugins configured by the scan profile have been enabled",
            "Please set the target URL",
            " | Use a profile.",
        )

        self.console = ConsoleUI(commands=commands_to_run, do_upd=False)
        self.console.sh()

        assert_result, msg = self.all_expected_substring_in_output(expected)
        self.assertTrue(assert_result, msg)

    def test_load_profile_by_filepath(self):
        with tempfile.NamedTemporaryFile(suffix=".pw3af") as tmp_profile:
            self._load_profile_by_filepath(tmp_profile.name)

    def _load_profile_by_filepath(self, profile_path):
        commands_to_run = ["profiles", "help", "use " + profile_path, "exit"]

        expected = (
            "The plugins configured by the scan profile have been enabled",
            "Please set the target URL",
            " | Use a profile.",
        )

        self.console = ConsoleUI(commands=commands_to_run, do_upd=False)
        self.console.sh()

        assert_result, msg = self.all_expected_substring_in_output(expected)
        self.assertTrue(assert_result, msg)

    def test_load_profile_not_exists(self):
        commands_to_run = ["profiles", "help", "use do_not_exist", "exit"]

        expected = ('The profile "do_not_exist.pw3af" wasn\'t found.',)

        self.console = ConsoleUI(commands=commands_to_run, do_upd=False)
        self.console.sh()

        assert_result, msg = self.startswith_expected_in_output(expected)
        self.assertTrue(assert_result, msg)

    def test_save_as_profile(self):
        commands_to_run = [
            "profiles",
            "use OWASP_TOP10",
            f"save_as {self.get_profile_name()}",
            "exit",
        ]

        expected = ("Profile saved.",)

        self.console = ConsoleUI(commands=commands_to_run, do_upd=False)
        self.console.sh()

        assert_result, msg = self.startswith_expected_in_output(expected)
        self.assertTrue(assert_result, msg)

        self._assert_exists(self.get_profile_name())
        self._assert_equal(self.get_profile_name(), "OWASP_TOP10")

    def test_save_as_self_contained_profile(self):
        commands_to_run = [
            "profiles",
            "use OWASP_TOP10",
            f"save_as {self.get_profile_name()} self-contained",
            "exit",
        ]

        expected = ("Profile saved.",)

        self.console = ConsoleUI(commands=commands_to_run, do_upd=False)
        self.console.sh()

        assert_result, msg = self.startswith_expected_in_output(expected)
        self.assertTrue(assert_result, msg)

        # The profile is now self contained
        p = profile(self.get_profile_name())
        self.assertTrue(
            p._config.get("audit.ssl_certificate", "ca_file_name").startswith(
                "base64://"
            )
        )

        # Before it wasn't
        p = profile("OWASP_TOP10")
        self.assertTrue(
            p._config.get("audit.ssl_certificate", "ca_file_name").startswith(
                "%ROOT_PATH%"
            )
        )

    def test_use_self_contained_profile(self):
        """
        Makes sure that we're able to use a self-contained profile and that
        it's transparent for the plugin code.
        """
        #
        #   Make the profile self-contained and load it
        #
        commands_to_run = [
            "profiles",
            "use OWASP_TOP10",
            f"save_as {self.get_profile_name()} self-contained",
            "back",
            "profiles",
            f"use {self.get_profile_name()}",
            "back",
            "plugins audit config ssl_certificate",
            "view",
            "exit",
        ]

        self.console = ConsoleUI(commands=commands_to_run, do_upd=False)
        self.console.sh()

        create_temp_dir()
        try:
            saved_profile = profile(self.get_profile_name())
            plugin = self.console._w3af.plugins.get_quick_instance(
                "audit", "ssl_certificate"
            )
            options = saved_profile.get_plugin_options(
                "audit", "ssl_certificate", plugin.get_options()
            )
            certificate_path = options["ca_file_name"].get_value()
            with open(certificate_path, "rb") as certificate_file:
                self.assertIn(
                    b"Bundle of CA Root Certificates", certificate_file.read()
                )
        finally:
            remove_temp_dir(ignore_errors=True)

    def test_set_save_use(self):
        """
        This is a unittest for the bug reported by a user where his settings
        are not saved to the profile.

        https://github.com/andresriancho/w3af/issues/291

        Actually, the settings are saved but not properly displayed, but that's
        not so important. The important thing is that the user was seeing the
        old setting instead of the new.
        """
        # We want to get the prompt, not a disclaimer message, and the spawned
        # w3af_console must start regardless of this machine's dependencies.
        startup_cfg = StartUpConfig()
        startup_cfg.accepted_disclaimer = True
        startup_cfg.skip_dependencies_check = True
        startup_cfg.save()

        # Load an existing profile, modify msf_location and save it as unittest
        commands_to_run = [
            "profiles",
            "use OWASP_TOP10",
            "back",
            "misc-settings",
            "set msf_location /tmp/",
            "back",
            "profiles",
            f"save_as {self.get_profile_name()}",
            "exit",
        ]

        self.console = ConsoleUI(commands=commands_to_run, do_upd=False)
        self.console.sh()

        expected = ("Profile saved.",)

        assert_result, msg = self.startswith_expected_in_output(expected)
        self.assertTrue(assert_result, msg)

        # The easy way to do this was to simply pass 'python' to Popen
        # but now that we want to run the tests in virtualenv, we need to
        # find the "correct" / "virtual" python executable using which and
        # then pass that one to Popen
        python_executable = sys.executable

        p = subprocess.Popen(
            [python_executable, "w3af_console", "-n"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE,
            shell=False,
            universal_newlines=True,
        )

        # Now we run a new ConsoleUI that will load the saved settings. We
        # should see /tmp/ as the value for msf_location
        commands_to_run = [
            "profiles",
            f"use {self.get_profile_name()}",
            "back",
            "misc-settings",
            "view",
            "back",
            "exit",
        ]

        expected_output = "/tmp"

        stdout, _stderr = p.communicate("\r".join(commands_to_run) + "\r")

        msg = 'Failed to find "%s" in "%s" using "%s" as python executable.'
        msg = msg % (expected_output, stdout, python_executable)
        self.assertIn(expected_output, stdout, msg)

    def test_save_as_profile_no_param(self):
        commands_to_run = ["profiles", "use OWASP_TOP10", "save_as", "exit"]

        expected = ("Parameter missing, please see the help",)

        self.console = ConsoleUI(commands=commands_to_run, do_upd=False)
        self.console.sh()

        assert_result, msg = self.startswith_expected_in_output(expected)
        self.assertTrue(assert_result, msg)

    def test_save_load_misc_settings(self):
        # Save the settings
        commands_to_run = [
            "misc-settings set msf_location /etc/",
            f"profiles save_as {self.get_profile_name()}",
            "exit",
        ]

        expected = ("Profile saved.",)

        self.console = ConsoleUI(commands=commands_to_run, do_upd=False)
        self.console.sh()

        assert_result, msg = self.startswith_expected_in_output(expected)
        self.assertTrue(assert_result, msg)

        self._assert_exists(self.get_profile_name())

        # Clean the captured stdout
        self._captured_stdout.clear()

        # Load the settings
        commands_to_run = [
            "profiles",
            f"use {self.get_profile_name()}",
            "back",
            "misc-settings view",
            "exit",
        ]

        expected = ("/etc/",)

        self.console = ConsoleUI(commands=commands_to_run, do_upd=False)
        self.console.sh()

        assert_result, msg = self.all_expected_substring_in_output(expected)
        self.assertTrue(assert_result, msg)
