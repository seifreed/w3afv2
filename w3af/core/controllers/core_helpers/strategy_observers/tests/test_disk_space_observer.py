"""
test_disk_space_observer.py

Copyright 2015 Andres Riancho

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

import errno
import os
import tempfile
import time
import unittest

from ..disk_space_observer import DiskSpaceObserver

HOME_DIR_VARIABLE = "W3AF_HOME_DIR"


class TestDiskSpaceObserver(unittest.TestCase):

    def set_home_dir(self, path):
        previous = os.environ.get(HOME_DIR_VARIABLE)
        os.environ[HOME_DIR_VARIABLE] = path

        if previous is None:
            self.addCleanup(os.environ.pop, HOME_DIR_VARIABLE)
        else:
            self.addCleanup(os.environ.__setitem__, HOME_DIR_VARIABLE, previous)

    def test_not_raises_time_protection(self):
        observer = DiskSpaceObserver()
        observer.last_call = time.time()
        observer.MIN_FREE_BYTES = (2**52) * 1024 * 1024
        observer.analyze_disk_space()

    def test_not_raises_low_requirement(self):
        observer = DiskSpaceObserver()
        observer.MIN_FREE_BYTES = 1
        observer.analyze_disk_space()

        self.assertGreater(observer.last_call, 0)

    def test_raises(self):
        observer = DiskSpaceObserver()
        observer.MIN_FREE_BYTES = (2**52) * 1024 * 1024

        with self.assertRaises(OSError) as context:
            observer.analyze_disk_space()

        self.assertEqual(context.exception.errno, errno.ENOSPC)

    def test_ignores_errors_reading_the_disk_usage(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            missing_home = os.path.join(temp_dir, "missing")

        self.set_home_dir(missing_home)

        observer = DiskSpaceObserver()
        observer.MIN_FREE_BYTES = (2**52) * 1024 * 1024
        observer.analyze_disk_space()

    def test_hooks_analyze_disk_space(self):
        observer = DiskSpaceObserver()
        observer.MIN_FREE_BYTES = (2**52) * 1024 * 1024

        for hook in (observer.crawl, observer.audit, observer.bruteforce):
            observer.last_call = 0
            self.assertRaises(OSError, hook, None, None)

        observer.last_call = 0
        self.assertRaises(OSError, observer.grep, None, None, None)
