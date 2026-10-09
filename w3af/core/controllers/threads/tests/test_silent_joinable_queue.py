"""
test_silent_joinable_queue.py

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

import multiprocessing
import unittest

from w3af.core.controllers.threads.silent_joinable_queue import SilentJoinableQueue


class TestSilentJoinableQueue(unittest.TestCase):

    def test_ignores_broken_pipes_and_works_as_a_joinable_queue(self):
        work_queue = SilentJoinableQueue(ctx=multiprocessing.get_context())
        self.addCleanup(work_queue.join_thread)
        self.addCleanup(work_queue.close)

        self.assertTrue(work_queue._ignore_epipe)

        work_queue.put("message")
        self.assertEqual(work_queue.get(timeout=10), "message")
        work_queue.task_done()
        work_queue.join()
