"""
test_phishtank_xml_parsing.py

Copyright 2006 Andres Riancho

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

import unittest

MEMORY_USAGE_SKIP = "This method is awful in terms of memory usage"


class TestPhishTankParseMethods(unittest.TestCase):
    @unittest.skip(MEMORY_USAGE_SKIP)
    def test_target_parser(self):
        pass

    @unittest.skip(MEMORY_USAGE_SKIP)
    def test_iterparse(self):
        pass

    @unittest.skip(
        "This method is awful in terms of memory usage, even with the calls to"
        " elem.clear() which I hoped would improve it. This solution also has"
        " the issue of being awfully slow."
    )
    def test_iterparse_remove_unused(self):
        pass
