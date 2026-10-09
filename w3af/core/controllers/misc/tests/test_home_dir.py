"""
test_home_dir.py

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
import tempfile
import unittest

from w3af.core.controllers.misc.home_dir import (
    DEFAULT_PROFILES_PATHS,
    copy_default_profiles,
    create_home_dir,
    ensure_dir,
    verify_dir_has_perm,
)


def touch(path):
    open(path, "w").close()


class TemporaryDirectoryTestCase(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.tmp = directory.name


class TestCreateHomeDir(TemporaryDirectoryTestCase):
    def use_home(self, home):
        previous = os.environ.get("W3AF_HOME_DIR")
        os.environ["W3AF_HOME_DIR"] = home
        self.addCleanup(self.restore_home, previous)

    @staticmethod
    def restore_home(previous):
        if previous is None:
            del os.environ["W3AF_HOME_DIR"]
        else:
            os.environ["W3AF_HOME_DIR"] = previous

    def test_creates_home_webroot_and_profiles(self):
        home = os.path.join(self.tmp, ".w3af")
        self.use_home(home)

        self.assertTrue(create_home_dir())
        self.assertTrue(os.path.isdir(os.path.join(home, "webroot")))
        self.assertIn("fast_scan.pw3af", os.listdir(os.path.join(home, "profiles")))

        self.assertTrue(create_home_dir())

    def test_home_below_a_file(self):
        touch(os.path.join(self.tmp, "file"))
        self.use_home(os.path.join(self.tmp, "file", ".w3af"))

        self.assertFalse(create_home_dir())

    def test_webroot_is_a_file(self):
        touch(os.path.join(self.tmp, "webroot"))
        self.use_home(self.tmp)

        self.assertFalse(create_home_dir())


class TestEnsureDir(TemporaryDirectoryTestCase):
    def test_creates_nested_directories(self):
        path = os.path.join(self.tmp, "a", "b")

        self.assertTrue(ensure_dir(path))
        self.assertTrue(ensure_dir(path))
        self.assertTrue(os.path.isdir(path))


class TestCopyDefaultProfiles(TemporaryDirectoryTestCase):
    def test_default_profile_paths_include_the_repository(self):
        self.assertTrue(any(os.path.isdir(p) for p in DEFAULT_PROFILES_PATHS))

    def test_skips_missing_candidates(self):
        source = os.path.join(self.tmp, "source")
        os.mkdir(source)
        touch(os.path.join(source, "custom.pw3af"))
        target = os.path.join(self.tmp, "profiles")

        candidates = (os.path.join(self.tmp, "missing"), source)

        self.assertTrue(copy_default_profiles(target, candidates))
        self.assertEqual(os.listdir(target), ["custom.pw3af"])

    def test_no_candidate_exists(self):
        target = os.path.join(self.tmp, "profiles")

        self.assertFalse(
            copy_default_profiles(target, (os.path.join(self.tmp, "missing"),))
        )

    def test_copy_fails(self):
        touch(os.path.join(self.tmp, "file"))
        target = os.path.join(self.tmp, "file", "profiles")

        self.assertFalse(copy_default_profiles(target, (self.tmp,)))


class TestVerifyDirHasPerm(TemporaryDirectoryTestCase):
    def test_missing_path(self):
        missing = os.path.join(self.tmp, "missing")

        self.assertRaises(RuntimeError, verify_dir_has_perm, missing, os.R_OK)

    def test_only_the_directory_itself(self):
        self.assertTrue(verify_dir_has_perm(self.tmp, os.R_OK | os.W_OK))

    def test_walks_the_requested_levels(self):
        deep = os.path.join(self.tmp, "one", "two", "three")
        os.makedirs(deep)
        touch(os.path.join(deep, "too-deep.txt"))
        os.chmod(os.path.join(deep, "too-deep.txt"), 0)

        self.assertTrue(verify_dir_has_perm(self.tmp, os.R_OK, levels=1))

    def test_git_directories_are_ignored(self):
        git_dir = os.path.join(self.tmp, ".git")
        os.mkdir(git_dir)
        touch(os.path.join(git_dir, "index"))
        os.chmod(os.path.join(git_dir, "index"), 0)

        self.assertTrue(verify_dir_has_perm(self.tmp, os.R_OK, levels=2))

    def test_file_without_permission(self):
        unreadable = os.path.join(self.tmp, "secret.txt")
        touch(unreadable)
        os.chmod(unreadable, 0)
        self.addCleanup(os.chmod, unreadable, 0o600)

        self.assertFalse(verify_dir_has_perm(self.tmp, os.R_OK, levels=1))
