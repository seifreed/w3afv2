# -*- coding: UTF-8 -*-
"""
test_profile.py

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

import shutil
import tempfile
import unittest
from pathlib import Path

from w3af.core.data.profile.profile import profile


class TestProfiles(unittest.TestCase):

    def test_load_profile_using_name_in_file(self):
        p = profile("OWASP_TOP10", workdir=".")
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "OWASP_TOP10.pw3af"
            shutil.copyfile(p.profile_file_name, target)
            profile_content = target.read_text(encoding="utf-8")
            target.write_text(
                profile_content.replace("name = OWASP_TOP10", "name = foobar"),
                encoding="utf-8",
            )

            loaded = profile("foobar", workdir=temp_dir)
            self.assertEqual(str(target), loaded.profile_file_name)

    def test_remove_profile_using_name_in_file(self):
        p = profile("OWASP_TOP10", workdir=".")
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "OWASP_TOP10.pw3af"
            shutil.copyfile(p.profile_file_name, target)
            profile_content = target.read_text(encoding="utf-8")
            target.write_text(
                profile_content.replace("name = OWASP_TOP10", "name = foobar"),
                encoding="utf-8",
            )

            loaded = profile("foobar", workdir=temp_dir)
            loaded.remove()

            self.assertFalse(target.exists())
