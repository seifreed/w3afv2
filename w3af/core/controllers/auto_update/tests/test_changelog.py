"""
test_changelog.py

Copyright 2013 Andres Riancho

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

from w3af.core.controllers.auto_update.changelog import ChangeLog
from w3af.core.controllers.auto_update.tests.local_git_repo import (
    commit_file,
    delete_file,
    init_repo,
)


class TestChangeLog(unittest.TestCase):

    def setUp(self):
        self._tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp_dir.cleanup)

        self.repo = init_repo(os.path.join(self._tmp_dir.name, "repo"))
        commit_file(self.repo, "old.txt", "old", "Add old.txt")
        self.start = commit_file(self.repo, "deps.py", "deps = []", "Add deps")
        self.modify_id = commit_file(
            self.repo, "deps.py", "deps = [1]", "Minor improvement for deps."
        )
        commit_file(self.repo, "new.txt", "new", "Add new.txt")
        self.end = delete_file(self.repo, "old.txt", "Remove old.txt")

        self.changelog = ChangeLog(self.start, self.end, self.repo.working_tree_dir)

    def test_changes_between(self):
        changes = self.changelog.get_changes()

        self.assertIsInstance(changes, list)
        self.assertEqual(len(changes), 3)

        first_commit = changes[0]
        self.assertEqual(first_commit.commit_id, self.end)
        self.assertEqual(first_commit.summary, "Remove old.txt")

        last_commit = changes[-1]
        self.assertEqual(last_commit.commit_id, self.modify_id)
        self.assertEqual(last_commit.summary, "Minor improvement for deps.")
        self.assertEqual(last_commit.changes, [("M", "deps.py")])

    def test_str(self):
        changelog_str = str(self.changelog)

        self.assertTrue(changelog_str.startswith(self.end[:10] + ": Remove old.txt"))
        self.assertIn("    A new.txt", changelog_str)
        self.assertIn("    M deps.py", changelog_str)
