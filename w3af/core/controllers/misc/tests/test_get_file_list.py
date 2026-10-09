"""
test_get_file_list.py

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
import unittest

from w3af import ROOT_PATH
from w3af.core.controllers.misc.get_file_list import get_file_list


class TestGetFileList(unittest.TestCase):
    def test_audit_plugins(self):
        plugins = get_file_list(os.path.join(ROOT_PATH, "plugins", "audit"))

        self.assertIn("sqli", plugins)
        self.assertNotIn("__init__", plugins)
        self.assertEqual(plugins, sorted(plugins))

    def test_custom_extension(self):
        with tempfile.TemporaryDirectory() as directory:
            for name in ("b.pw3af", "a.pw3af", "c.py", "__init__.pw3af"):
                open(os.path.join(directory, name), "w").close()

            self.assertEqual(get_file_list(directory, ".pw3af"), ["a", "b"])
