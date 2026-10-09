"""
test_file_lock.py

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
import threading
import unittest

from w3af.core.controllers.misc.file_lock import FileLock, FileLockException


class TestFileLock(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.target = os.path.join(directory.name, "plugin.py")

    def test_acquire_creates_and_release_removes_lockfile(self):
        lock = FileLock(self.target)

        lock.acquire()
        self.assertTrue(lock.is_locked)
        self.assertTrue(os.path.exists(f"{self.target}.lock"))

        lock.release()
        self.assertFalse(lock.is_locked)
        self.assertFalse(os.path.exists(f"{self.target}.lock"))

    def test_context_manager(self):
        with FileLock(self.target) as lock:
            self.assertTrue(lock.is_locked)

        self.assertFalse(lock.is_locked)
        self.assertFalse(os.path.exists(lock.lockfile))

    def test_entering_an_acquired_lock_keeps_it(self):
        lock = FileLock(self.target)
        lock.acquire()

        with lock:
            self.assertTrue(lock.is_locked)

        self.assertFalse(lock.is_locked)

    def test_exit_after_manual_release(self):
        with FileLock(self.target) as lock:
            lock.release()

        self.assertFalse(lock.is_locked)

    def test_second_lock_times_out(self):
        with FileLock(self.target):
            contender = FileLock(self.target, timeout=0.2, delay=0.05)
            self.assertRaises(FileLockException, contender.acquire)

    def test_second_lock_waits_for_release(self):
        first = FileLock(self.target)
        first.acquire()
        threading.Timer(0.1, first.release).start()

        with FileLock(self.target, timeout=5, delay=0.02) as second:
            self.assertTrue(second.is_locked)

    def test_unexpected_os_errors_are_raised(self):
        lock = FileLock(os.path.join(self.target, "missing-dir", "plugin.py"))

        self.assertRaises(FileNotFoundError, lock.acquire)

    def test_release_tolerates_a_closed_descriptor(self):
        lock = FileLock(self.target)
        lock.acquire()
        os.close(lock.fd)

        lock.release()

        self.assertFalse(os.path.exists(lock.lockfile))

    def test_garbage_collected_lock_removes_lockfile(self):
        lock = FileLock(self.target)
        lock.acquire()
        lockfile = lock.lockfile

        del lock

        self.assertFalse(os.path.exists(lockfile))
