"""
test_monkey_patch_debug.py

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

import multiprocessing.util
import unittest

import w3af.core.controllers.output_manager as om
from w3af.core.controllers.tests.recording_output import start_recording_output
from w3af.core.controllers.threads import pool276, threadpool
from w3af.core.controllers.threads.monkey_patch_debug import (
    ORIGINAL_DEBUG,
    monkey_patch_debug,
    new_debug,
    remove_monkey_patch_debug,
)
from w3af.core.controllers.threads.threadpool import Pool


class TestMonkeyPatchDebug(unittest.TestCase):

    def setUp(self):
        self.recorder = start_recording_output()
        self.addCleanup(om.manager.get_output_plugin_inst().remove, self.recorder)
        self.addCleanup(remove_monkey_patch_debug)

    def test_patch_sends_pool_debug_to_output_manager(self):
        monkey_patch_debug()

        for module in (multiprocessing.util, threadpool, pool276):
            self.assertIs(module.debug, new_debug)

        pool = Pool(1)
        pool.terminate_join()

        debug_messages = self.recorder.messages_of("debug")
        self.assertIn("[threadpool] terminating pool", debug_messages)
        self.assertIn("[threadpool] added worker", debug_messages)

    def test_remove_restores_original_debug(self):
        monkey_patch_debug()
        remove_monkey_patch_debug()

        for module in (multiprocessing.util, threadpool, pool276):
            self.assertIs(module.debug, ORIGINAL_DEBUG)

    def test_new_debug_formats_arguments(self):
        new_debug("%s workers", 3)
        self.assertIn("[threadpool] 3 workers", self.recorder.messages_of("debug"))
