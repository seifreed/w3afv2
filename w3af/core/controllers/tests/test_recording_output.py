"""
test_recording_output.py

Copyright 2026 w3af contributors

This file is part of w3af, http://w3af.org/ .

w3af is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; version 2 of the License.

w3af is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with w3af; if not, write to the Free Software
Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301 USA

"""

import unittest

from w3af.core.controllers.output_manager.manager import OutputManager
from w3af.core.controllers.tests.recording_output import start_recording_output


class TestRecordingOutput(unittest.TestCase):
    def test_start_replaces_previous_recording_plugins(self):
        manager = OutputManager()
        self.addCleanup(manager.stop)

        first = start_recording_output(manager)
        second = start_recording_output(manager)

        self.assertIsNot(first, second)
        self.assertEqual(manager.get_output_plugin_inst(), [second])
