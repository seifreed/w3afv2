"""
test_git_auto_update.py

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

import git

from w3af.core.controllers.auto_update.tests.local_git_repo import (
    commit_file,
    init_repo,
    write_file,
)
from w3af.core.controllers.auto_update.utils import (
    DETACHED_HEAD,
    get_commit_id_date,
    get_current_branch,
    get_latest_commit,
    get_latest_commit_date,
    is_dirty_repo,
    is_git_repo,
    repo_has_conflicts,
    to_short_id,
)


class TestGitUtils(unittest.TestCase):

    def setUp(self):
        self._tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp_dir.cleanup)

        self.repo_path = os.path.join(self._tmp_dir.name, "repo")
        self.not_repo_path = os.path.join(self._tmp_dir.name, "plain")
        os.mkdir(self.not_repo_path)

        self.repo = init_repo(self.repo_path)
        self.first_id = commit_file(self.repo, "a.txt", "1", "First")
        self.second_id = commit_file(self.repo, "a.txt", "2", "Second")

    def test_to_short_id(self):
        self.assertEqual(to_short_id(self.first_id), self.first_id[:10])

    def test_is_git_repo(self):
        self.assertTrue(is_git_repo(self.repo_path))

    def test_is_git_repo_negative(self):
        self.assertFalse(is_git_repo(self.not_repo_path))

    def test_is_dirty_repo(self):
        self.assertFalse(is_dirty_repo(self.repo_path))

        write_file(self.repo, "a.txt", "dirty")

        self.assertTrue(is_dirty_repo(self.repo_path))

    def test_is_dirty_repo_negative(self):
        self.assertFalse(is_dirty_repo(self.not_repo_path))

    def test_get_latest_commit(self):
        self.assertEqual(get_latest_commit(self.repo_path), self.second_id)

    def test_get_latest_commit_negative(self):
        self.assertRaises(
            git.exc.InvalidGitRepositoryError, get_latest_commit, self.not_repo_path
        )

    def test_get_commit_id_date(self):
        expected = get_latest_commit_date(self.repo_path)

        self.assertEqual(get_commit_id_date(self.second_id, self.repo_path), expected)

    def test_get_commit_id_date_unknown_commit(self):
        self.assertIsNone(get_commit_id_date(self.first_id, self.repo_path))

    def test_get_current_branch(self):
        self.repo.create_head("feature-x").checkout()

        self.assertEqual(get_current_branch(self.repo_path), "feature-x")

    def test_get_current_branch_detached_head(self):
        self.repo.git.checkout(self.first_id)

        self.assertEqual(get_current_branch(self.repo_path), DETACHED_HEAD)

    def test_repo_has_no_conflicts(self):
        self.assertFalse(repo_has_conflicts(self.repo_path))
