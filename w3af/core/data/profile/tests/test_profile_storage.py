"""
test_profile_storage.py

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

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from w3af.core.controllers.misc_settings import MiscSettings
from w3af.core.data.options.opt_factory import opt_factory
from w3af.core.data.options.option_list import OptionList
from w3af.core.data.profile.profile import profile
from w3af.core.exceptions import BaseFrameworkException

PROFILE = """\
[profile]
name = {name}
description = Profile used by the unit tests
"""


class ProfileTestCase(unittest.TestCase):
    """
    Every test gets its own w3af home directory (configured through the
    W3AF_HOME_DIR environment variable read by get_home_dir) and its own
    working directory.
    """

    def setUp(self):
        self.home = Path(tempfile.mkdtemp())
        self.workdir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.home)
        self.addCleanup(shutil.rmtree, self.workdir)

        self.addCleanup(self.restore_environment, os.environ.copy())
        os.environ["W3AF_HOME_DIR"] = str(self.home)

    @staticmethod
    def restore_environment(environment):
        os.environ.clear()
        os.environ.update(environment)

    def write_profile(self, directory, file_name, content):
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / file_name
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")
        return path


class TestProfileLocation(ProfileTestCase):
    def test_load_by_path(self):
        path = self.write_profile(self.workdir, "a.pw3af", PROFILE.format(name="a"))

        loaded = profile(str(path))

        self.assertEqual(loaded.get_profile_file(), str(path))
        self.assertEqual(loaded.get_name(), "a")

    def test_load_from_workdir(self):
        path = self.write_profile(self.workdir, "a.pw3af", PROFILE.format(name="a"))

        loaded = profile("a", workdir=str(self.workdir))

        self.assertEqual(loaded.get_profile_file(), str(path))

    def test_load_from_workdir_profiles_directory(self):
        path = self.write_profile(
            self.workdir / "profiles", "a.pw3af", PROFILE.format(name="a")
        )

        loaded = profile("a", workdir=str(self.workdir))

        self.assertEqual(loaded.get_profile_file(), str(path))

    def test_load_from_home_profiles_directory(self):
        path = self.write_profile(
            self.home / "profiles", "a.pw3af", PROFILE.format(name="a")
        )

        loaded = profile("a", workdir=str(self.workdir / "missing"))

        self.assertEqual(loaded.get_profile_file(), str(path))

    def test_name_detection_skips_unreadable_profiles(self):
        directory = self.workdir
        self.write_profile(directory, "notes.txt", PROFILE.format(name="wanted"))
        self.write_profile(directory, "binary.pw3af", b"\xff\xfe[profile]\n")
        self.write_profile(directory, "no_name.pw3af", "[audit.xss]\n")

        # Every candidate is inspected (and skipped) before giving up
        self.assertRaises(
            BaseFrameworkException, profile, "wanted", workdir=str(directory)
        )

        path = self.write_profile(
            directory, "renamed.pw3af", PROFILE.format(name="wanted")
        )

        loaded = profile("wanted", workdir=str(directory))

        self.assertEqual(loaded.get_profile_file(), str(path))

    def test_not_found(self):
        with self.assertRaises(BaseFrameworkException) as context:
            profile("missing", workdir=str(self.workdir))

        self.assertIn(
            'The profile "missing.pw3af" wasn\'t found.', str(context.exception)
        )

    def test_invalid_profile_files(self):
        malformed = self.write_profile(self.workdir, "m.pw3af", "no section header")
        binary = self.write_profile(self.workdir, "b.pw3af", b"[profile]\n\xff\n")
        unnamed = self.write_profile(self.workdir, "u.pw3af", "[profile]\n")

        with self.assertRaises(BaseFrameworkException) as context:
            profile(str(malformed))
        self.assertIn("ConfigParser error in profile", str(context.exception))

        with self.assertRaises(BaseFrameworkException) as context:
            profile(str(binary))
        self.assertIn("Unknown error in profile", str(context.exception))

        with self.assertRaises(BaseFrameworkException) as context:
            profile(str(unnamed))
        self.assertIn("does NOT contain a [profile] section", str(context.exception))

    def test_is_valid_profile_name(self):
        self.assertTrue(profile.is_valid_profile_name("fast_scan-2"))
        self.assertRaises(
            BaseFrameworkException, profile.is_valid_profile_name, "fast scan"
        )


class TestProfileStorage(ProfileTestCase):
    def test_save_requires_a_file_name(self):
        self.assertRaises(BaseFrameworkException, profile().save)

    def test_save_in_home_profiles_directory(self):
        (self.home / "profiles").mkdir()
        new_profile = profile()
        new_profile.set_name("saved")

        new_profile.save("saved")

        expected = self.home / "profiles" / "saved.pw3af"
        self.assertEqual(new_profile.get_profile_file(), str(expected))
        self.assertEqual(profile("saved").get_name(), "saved")

    def test_save_with_full_path(self):
        path = self.workdir / "full.pw3af"
        new_profile = profile()
        new_profile.set_name("full")

        new_profile.save(str(path))

        self.assertEqual(profile(str(path)).get_name(), "full")

    def test_save_to_missing_directory(self):
        new_profile = profile()

        with self.assertRaises(BaseFrameworkException) as context:
            new_profile.save(str(self.workdir / "missing" / "p.pw3af"))

        self.assertIn("Failed to open profile file", str(context.exception))

    def test_remove(self):
        path = self.write_profile(self.workdir, "r.pw3af", PROFILE.format(name="r"))
        loaded = profile(str(path))

        self.assertTrue(loaded.remove())
        self.assertFalse(path.exists())
        self.assertRaises(BaseFrameworkException, loaded.remove)


class TestProfileSettings(ProfileTestCase):
    def setUp(self):
        super().setUp()
        self.profile = profile()

    def test_name_and_description(self):
        self.assertIsNone(self.profile.get_name())
        self.assertIsNone(self.profile.get_desc())

        self.profile.set_desc("A description")
        self.profile.set_name("A name")

        self.assertEqual(self.profile.get_name(), "A name")
        self.assertEqual(self.profile.get_desc(), "A description")

    def test_enabled_plugins(self):
        self.profile.set_name("plugins")
        self.profile.set_enabled_plugins("audit", ["xss", "sqli"])
        self.profile.set_enabled_plugins("audit", ["sqli", "os_commanding"])
        self.profile.set_enabled_plugins("crawl", ["web_spider"])

        self.assertEqual(
            self.profile.get_enabled_plugins("audit"), ["sqli", "os_commanding"]
        )
        self.assertEqual(self.profile.get_enabled_plugins("crawl"), ["web_spider"])

    def test_plugin_options(self):
        options = OptionList()
        options.add(opt_factory("timeout", 10, "Timeout", "integer"))
        options.add(opt_factory("words", "a,b", "Words", "list"))
        self.profile.set_name("plugin options")

        self.profile.set_plugin_options("crawl", "web_spider", options)
        options["timeout"].set_value(30)
        self.profile.set_plugin_options("crawl", "web_spider", options)
        self.profile.set_plugin_options("audit", "web_spider", OptionList())

        defaults = OptionList()
        defaults.add(opt_factory("timeout", 10, "Timeout", "integer"))
        defaults.add(opt_factory("words", "", "Words", "list"))
        loaded = self.profile.get_plugin_options("crawl", "web_spider", defaults)

        self.assertEqual(loaded["timeout"].get_value(), 30)
        self.assertEqual(loaded["words"].get_value(), ["a", "b"])

    def test_misc_settings(self):
        misc_settings = MiscSettings()
        options = misc_settings.get_options()
        options["fuzzed_files_extension"].set_value("jpg")

        self.assertEqual(
            self.profile.get_misc_settings(misc_settings)[
                "fuzzed_files_extension"
            ].get_value(),
            misc_settings.get_options()["fuzzed_files_extension"].get_value(),
        )

        self.profile.set_misc_settings(options)
        self.profile.set_misc_settings(options)

        loaded = self.profile.get_misc_settings(misc_settings)
        self.assertEqual(loaded["fuzzed_files_extension"].get_value(), "jpg")

    def test_http_settings(self):
        options = self.profile.get_http_settings()
        options["timeout"].set_value(17)

        self.profile.set_http_settings(options)

        self.assertEqual(self.profile.get_http_settings()["timeout"].get_value(), 17)

    def test_target(self):
        options = OptionList()
        options.add(opt_factory("target", "", "Target", "string"))

        self.profile.set_target("http://w3af.org/")
        self.profile.set_target("http://w3af.org/new/")
        self.profile.set_enabled_plugins("audit", ["xss"])

        target = self.profile.get_target(options)

        self.assertEqual(target["target"].get_value(), "http://w3af.org/new/")
