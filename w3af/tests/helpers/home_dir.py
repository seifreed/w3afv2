"""
home_dir.py

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
import shutil
import tempfile
import unittest

HOME_DIR_VARIABLE = "W3AF_HOME_DIR"


def use_temporary_home(test_case: unittest.TestCase) -> str:
    """
    Point the w3af home directory (profiles, startup.conf, certificates...)
    to a new temporary directory for the duration of test_case, so tests never
    read or write the user's ~/.w3af. Child processes inherit it.

    :return: The temporary home directory
    """
    home = tempfile.mkdtemp(prefix="w3af-home-")
    environ = dict(os.environ)

    # Cleanups run in reverse order: restore the environment, then remove
    test_case.addCleanup(shutil.rmtree, home, ignore_errors=True)
    test_case.addCleanup(os.environ.update, environ)
    test_case.addCleanup(os.environ.clear)

    os.environ[HOME_DIR_VARIABLE] = home
    return home
