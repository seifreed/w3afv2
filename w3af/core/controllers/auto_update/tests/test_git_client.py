"""
test_git_client.py

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
import shutil
import tempfile
import unittest

from w3af.core.controllers.auto_update.changelog import ChangeLog
from w3af.core.controllers.auto_update.git_client import (
    GitClient,
    GitClientError,
    GitRemoteProgress,
)
from w3af.core.controllers.auto_update.tests.local_git_repo import (
    CallRecorder,
    clone_repo,
    commit_file,
    init_repo,
)


class TestGitClient(unittest.TestCase):

    def setUp(self):
        self._tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp_dir.cleanup)

        self.upstream = init_repo(os.path.join(self._tmp_dir.name, "upstream"))
        self.first_id = commit_file(self.upstream, "a.txt", "1", "First")
        self.second_id = commit_file(self.upstream, "a.txt", "2", "Second")

        self.local = clone_repo(
            self.upstream, os.path.join(self._tmp_dir.name, "local")
        )
        self.client = GitClient(self.local.working_tree_dir)

    def test_url_is_origin_remote(self):
        self.assertEqual(self.client.URL, self.upstream.working_tree_dir)

    def test_get_local_head_id(self):
        self.assertEqual(self.client.get_local_head_id(), self.second_id)

    def test_get_remote_head_id_fetches_new_commits(self):
        third_id = commit_file(self.upstream, "a.txt", "3", "Third")

        self.assertEqual(self.client.get_remote_head_id(), third_id)
        self.assertEqual(self.client.get_local_head_id(), self.second_id)

    def test_get_parent_for_revision(self):
        parents = self.client.get_parent_for_revision(self.second_id)

        self.assertEqual(parents, [self.first_id])

    def test_reset_to_previous_state(self):
        self.client.reset_to_previous_state(self.first_id)

        self.assertEqual(self.local.head.commit.hexsha, self.first_id)
        self.assertFalse(self.local.is_dirty())

    def test_pull_returns_changelog_between_heads(self):
        third_id = commit_file(self.upstream, "a.txt", "3", "Third")

        changelog = self.client.pull()

        self.assertIsInstance(changelog, ChangeLog)
        self.assertEqual(changelog.start, self.second_id)
        self.assertEqual(changelog.end, third_id)
        self.assertEqual(self.local.head.commit.hexsha, third_id)

    def test_fetch_from_missing_remote_raises(self):
        shutil.rmtree(self.upstream.working_tree_dir)

        self.assertRaises(GitClientError, self.client.fetch)


class TestGitRemoteProgress(unittest.TestCase):

    def test_update_notifies_live_observers(self):
        recorder = CallRecorder()
        progress = GitRemoteProgress()
        progress.add_observer(recorder)

        progress.update(1, 2, 3, "message")

        self.assertEqual(recorder.calls, [(1, 2, 3, "message")])

    def test_update_notifies_bound_method_observers(self):
        recorder = CallRecorder()
        progress = GitRemoteProgress()
        progress.add_observer(recorder.__call__)

        progress.update(1, 2)

        self.assertEqual(recorder.calls, [(1, 2, None, "")])

    def test_update_skips_collected_observers(self):
        recorder = CallRecorder()
        progress = GitRemoteProgress()
        progress.add_observer(recorder)
        del recorder

        progress.update(1, 2)

    def test_observers_are_not_shared_between_instances(self):
        recorder = CallRecorder()
        GitRemoteProgress().add_observer(recorder)

        GitRemoteProgress().update(1, 2)

        self.assertEqual(recorder.calls, [])
