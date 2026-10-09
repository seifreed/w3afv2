"""
test_version_manager.py

Copyright 2011 Andres Riancho

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

import datetime
import gc
import os
import tempfile
import unittest
import weakref

from w3af.core.controllers.auto_update.changelog import ChangeLog
from w3af.core.controllers.auto_update.git_client import GitClient
from w3af.core.controllers.auto_update.tests.local_git_repo import (
    CallRecorder,
    clone_repo,
    commit_file,
    init_repo,
)
from w3af.core.controllers.auto_update.version_manager import VersionMgr
from w3af.core.data.db.startup_cfg import StartUpConfig


def days_ago(days):
    today = datetime.datetime.now().astimezone().date()
    return today - datetime.timedelta(days=days)


class TestVersionMgr(unittest.TestCase):

    def setUp(self):
        self._tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp_dir.cleanup)

        self.upstream = init_repo(self._path("upstream"))
        commit_file(self.upstream, "requirements.py", "deps = []", "Add deps")
        self.base_id = commit_file(self.upstream, "a.txt", "1", "Add a.txt")

        self.local = clone_repo(self.upstream, self._path("local"))

        self.start_cfg = StartUpConfig(self._path("startup.conf"))
        self.log = CallRecorder()
        self.vmgr = VersionMgr(
            self.local.working_tree_dir, self.log, start_cfg=self.start_cfg
        )

        self.on_update_check = CallRecorder()
        self.on_already_latest = CallRecorder()
        self.on_update = CallRecorder()
        self.on_added_dep = CallRecorder()
        self.vmgr.register(VersionMgr.ON_UPDATE_CHECK, self.on_update_check, None)
        self.vmgr.register(VersionMgr.ON_ALREADY_LATEST, self.on_already_latest, None)
        self.vmgr.register(VersionMgr.ON_UPDATE, self.on_update, None)
        self.vmgr.register(VersionMgr.ON_UPDATE_ADDED_DEP, self.on_added_dep, "dep")

    def _path(self, name):
        return os.path.join(self._tmp_dir.name, name)

    def _schedule_daily_update(self, last_update_days_ago):
        self.start_cfg._autoupd = True
        self.start_cfg._freq = StartUpConfig.FREQ_DAILY
        self.start_cfg._lastupd = days_ago(last_update_days_ago)

    def test_no_need_update(self):
        self.start_cfg._autoupd = False

        self.assertFalse(self.vmgr._has_to_update())

    def test_has_to_update(self):
        """
        Test [D]aily, [W]eekly and [M]onthly auto-update
        """
        for freq, diffdays in (
            (StartUpConfig.FREQ_DAILY, 1),
            (StartUpConfig.FREQ_WEEKLY, 8),
            (StartUpConfig.FREQ_MONTHLY, 34),
        ):
            self.start_cfg._autoupd = True
            self.start_cfg._freq = freq
            self.start_cfg._lastupd = days_ago(diffdays)

            self.assertTrue(self.vmgr._has_to_update())

    def test_has_not_to_update_within_frequency(self):
        for freq, diffdays in (
            (StartUpConfig.FREQ_DAILY, 0),
            (StartUpConfig.FREQ_WEEKLY, 6),
            (StartUpConfig.FREQ_MONTHLY, 29),
        ):
            self.start_cfg._autoupd = True
            self.start_cfg._freq = freq
            self.start_cfg._lastupd = days_ago(diffdays)

            self.assertFalse(self.vmgr._has_to_update())

    def test_added_new_dependencies(self):
        end = commit_file(self.upstream, "requirements.py", "deps = [1]", "Bump")
        changelog = ChangeLog(self.base_id, end, self.upstream.working_tree_dir)

        self.assertTrue(self.vmgr._added_new_dependencies(changelog))

    def test_not_added_new_dependencies(self):
        end = commit_file(self.upstream, "a.txt", "2", "Change a.txt")
        changelog = ChangeLog(self.base_id, end, self.upstream.working_tree_dir)

        self.assertFalse(self.vmgr._added_new_dependencies(changelog))

    def test_update_not_required_not_forced(self):
        """
        Test that we don't perform any extra steps if the local installation
        was already updated today.
        """
        self._schedule_daily_update(last_update_days_ago=0)

        self.assertIsNone(self.vmgr.update())

        self.assertEqual(self.on_update_check.calls, [])
        self.assertEqual(self.on_already_latest.calls, [])
        self.assertEqual(self.on_update.calls, [])

    def test_update_required_not_forced(self):
        """
        Test that we check if we're on the latest version if the latest
        local installation update was 3 days ago and the frequency is set to
        daily. The local repository is already in the latest version.
        """
        self._schedule_daily_update(last_update_days_ago=3)

        self.assertIsNone(self.vmgr.update())

        self.assertEqual(len(self.on_update_check.calls), 1)
        self.assertEqual(len(self.on_already_latest.calls), 1)
        self.assertEqual(self.on_update.calls, [])
        self.assertEqual(self.start_cfg.last_upd, days_ago(0))

    def test_update_required_outdated_not_forced(self):
        """
        Test that an outdated local repository is updated to the remote head
        when the user confirms the update.
        """
        added_dep_id = commit_file(
            self.upstream, "requirements.py", "deps = [1]", "Bump deps"
        )
        self._schedule_daily_update(last_update_days_ago=3)
        confirm = CallRecorder(return_value=True)
        self.vmgr.callback_onupdate_confirm = confirm

        changelog, start, end = self.vmgr.update()

        self.assertEqual((start, end), (self.base_id, added_dep_id))
        self.assertEqual((changelog.start, changelog.end), (start, end))
        self.assertEqual(self.local.head.commit.hexsha, added_dep_id)
        self.assertEqual(len(confirm.calls), 1)
        self.assertEqual(len(self.on_update_check.calls), 1)
        self.assertEqual(self.on_already_latest.calls, [])
        self.assertEqual(len(self.on_update.calls), 1)
        self.assertEqual(self.on_added_dep.calls, [("dep",)])
        self.assertEqual(self.start_cfg.last_commit_id, added_dep_id)

    def test_update_rejected_by_user(self):
        commit_file(self.upstream, "a.txt", "2", "Change a.txt")
        self.vmgr.callback_onupdate_confirm = CallRecorder(return_value=False)

        self.assertIsNone(self.vmgr.update(force=True))

        self.assertEqual(self.on_update.calls, [])
        self.assertEqual(self.local.head.commit.hexsha, self.base_id)

    def test_update_after_reset_to_previous_state(self):
        client = GitClient(self.local.working_tree_dir)
        parent_id = client.get_parent_for_revision(client.get_local_head_id())[0]
        client.reset_to_previous_state(parent_id)
        self.vmgr.callback_onupdate_confirm = CallRecorder(return_value=True)

        changelog, start, end = self.vmgr.update(force=True)

        self.assertEqual((start, end), (parent_id, self.base_id))
        self.assertEqual(self.on_added_dep.calls, [])
        self.assertIn("Add a.txt", str(changelog))

    def test_no_cycle_refs(self):
        """
        Without reference cycles the VersionMgr is released by reference
        counting alone, so it must die while the cycle collector is off.
        """
        gc.disable()
        self.addCleanup(gc.enable)

        vmgr = VersionMgr(
            self.local.working_tree_dir, self.log, start_cfg=self.start_cfg
        )
        vmgr_ref = weakref.ref(vmgr)
        del vmgr

        self.assertIsNone(vmgr_ref())
