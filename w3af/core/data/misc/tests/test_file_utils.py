"""
test_file_utils.py

Copyright 2006 Andres Riancho

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
import subprocess
import tempfile
import unittest
from datetime import date
from pathlib import Path

from w3af.core.data.misc.file_utils import (
    days_since_file_update,
    get_days_since_last_update,
    replace_file_special_chars,
)
from w3af.core.data.misc.local_date import local_today

COMMIT_DATE = "2014-06-21T10:20:31-0300"


class TestFileUtils(unittest.TestCase):
    """
    Each test runs inside a throwaway git repository whose only commit is
    dated COMMIT_DATE, so the results do not depend on when or where the
    suite runs.
    """

    def setUp(self):
        self.repo = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.repo)

        (self.repo / "tracked.txt").write_text("tracked\n")
        (self.repo / "folder").mkdir()
        (self.repo / "folder" / "inside.txt").write_text("inside\n")
        (self.repo / "untracked.txt").write_text("untracked\n")

        env = dict(
            os.environ,
            GIT_AUTHOR_NAME="w3af",
            GIT_AUTHOR_EMAIL="w3af@example.com",
            GIT_COMMITTER_NAME="w3af",
            GIT_COMMITTER_EMAIL="w3af@example.com",
            GIT_AUTHOR_DATE=COMMIT_DATE,
            GIT_COMMITTER_DATE=COMMIT_DATE,
        )
        for command in (
            ["git", "init", "-q"],
            ["git", "add", "tracked.txt", "folder"],
            ["git", "commit", "-q", "--no-gpg-sign", "-m", "fixture"],
        ):
            subprocess.run(command, cwd=self.repo, env=env, check=True)

        cwd = os.getcwd()
        os.chdir(self.repo)
        self.addCleanup(os.chdir, cwd)

        self.expected_days = (local_today() - date(2014, 6, 21)).days

    def test_get_days_since_last_update_file(self):
        self.assertEqual(get_days_since_last_update("tracked.txt"), self.expected_days)

    def test_get_days_since_last_update_directory(self):
        self.assertEqual(get_days_since_last_update("folder"), self.expected_days)

    def test_days_since_file_update_true(self):
        self.assertTrue(days_since_file_update("tracked.txt", 0))

    def test_days_since_file_update_false(self):
        self.assertFalse(days_since_file_update("tracked.txt", self.expected_days))

    def test_days_since_file_update_directory(self):
        self.assertTrue(days_since_file_update("folder", 0))

    def test_days_since_file_update_not_tracked(self):
        self.assertRaises(ValueError, days_since_file_update, "untracked.txt", 0)

    def test_days_since_file_update_outside_repository(self):
        outside = tempfile.mkdtemp()
        self.addCleanup(os.rmdir, outside)

        self.assertRaises(ValueError, days_since_file_update, outside, 0)

    def test_replace_file_special_chars(self):
        self.assertEqual(
            replace_file_special_chars("C:/w3af/scan:1.db"), "C_/w3af/scan_1.db"
        )
