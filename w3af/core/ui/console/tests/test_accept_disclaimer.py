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
import unittest
from contextlib import redirect_stdout

from w3af.core.data.db.startup_cfg import StartUpConfig
from w3af.core.ui.console.console_ui import ConsoleUI
from w3af.tests.helpers.home_dir import use_temporary_home


class TestAcceptDisclaimer(unittest.TestCase):

    def setUp(self):
        home = use_temporary_home(self)
        self.console_ui = ConsoleUI(do_upd=False)
        self.cfg_file = os.path.join(home, "startup.conf")
        self.questions = []

    def answer(self, response):
        def ask_user(question):
            self.questions.append(question)
            return response

        return ask_user

    def saved_decision(self):
        return StartUpConfig(self.cfg_file).accepted_disclaimer

    def test_not_saved_not_accepted(self):
        accepted = self.console_ui.accept_disclaimer(
            StartUpConfig(self.cfg_file), self.answer("")
        )

        self.assertFalse(accepted)
        self.assertEqual(len(self.questions), 1)
        self.assertFalse(self.saved_decision())

    def test_not_saved_accepted(self):
        accepted = self.console_ui.accept_disclaimer(
            StartUpConfig(self.cfg_file), self.answer("y")
        )

        self.assertTrue(accepted)
        self.assertTrue(self.saved_decision())

    def test_saved(self):
        startup_cfg = StartUpConfig(self.cfg_file)
        startup_cfg.accepted_disclaimer = True
        startup_cfg.save()

        accepted = self.console_ui.accept_disclaimer(
            StartUpConfig(self.cfg_file), self.answer("")
        )

        self.assertTrue(accepted)
        self.assertEqual(self.questions, [])

    def test_default_config_is_the_home_startup_config(self):
        accepted = self.console_ui.accept_disclaimer(ask_user=self.answer("yes"))

        self.assertTrue(accepted)
        self.assertTrue(self.saved_decision())

    def test_interrupted_answer_is_not_accepted(self):
        def interrupted(question):
            raise EOFError

        output = io.StringIO()
        with redirect_stdout(output):
            accepted = self.console_ui.accept_disclaimer(
                StartUpConfig(self.cfg_file), interrupted
            )

        self.assertFalse(accepted)
        self.assertEqual(output.getvalue(), "\n")
        self.assertFalse(self.saved_decision())
