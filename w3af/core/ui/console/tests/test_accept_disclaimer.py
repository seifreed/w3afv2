"""
Copyright 2012 Andres Riancho

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

import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

from w3af.core.data.db.startup_cfg import StartUpConfig
from w3af.core.ui.console.console_ui import ConsoleUI


class TestAcceptDisclaimer(unittest.TestCase):
    def setUp(self):
        fd, self._cfg_path = tempfile.mkstemp(suffix=".conf")
        os.close(fd)
        self.startup_cfg = StartUpConfig(cfg_file=self._cfg_path)
        self.console_ui = ConsoleUI(do_upd=False, startup_cfg=self.startup_cfg)
        self._old_stdin = sys.stdin

    def tearDown(self):
        sys.stdin = self._old_stdin
        os.remove(self._cfg_path)

    def _answer_disclaimer(self, answer):
        sys.stdin = io.StringIO(answer)
        output = io.StringIO()
        with redirect_stdout(output):
            return self.console_ui.accept_disclaimer()

    def test_not_saved_not_accepted(self):
        self.startup_cfg.set_accepted_disclaimer(False)
        self.assertFalse(self._answer_disclaimer("\n"))

    def test_not_saved_accepted(self):
        self.startup_cfg.set_accepted_disclaimer(False)
        self.assertTrue(self._answer_disclaimer("y\n"))

        # The acceptance is persisted so the question is not asked again
        reloaded = StartUpConfig(cfg_file=self._cfg_path)
        self.assertTrue(reloaded.accepted_disclaimer)

    def test_accepted_full_word(self):
        self.startup_cfg.set_accepted_disclaimer(False)
        self.assertTrue(self._answer_disclaimer("yes\n"))

    def test_not_accepted_on_eof(self):
        self.startup_cfg.set_accepted_disclaimer(False)
        self.assertFalse(self._answer_disclaimer(""))

    def test_saved(self):
        self.startup_cfg.set_accepted_disclaimer(True)
        self.assertTrue(self.console_ui.accept_disclaimer())
