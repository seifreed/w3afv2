"""
test_all.py

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

from w3af.core.data.constants.common_words import common_words
from w3af.core.data.constants.cookies import (
    ALL_COOKIES,
    COOKIE_FINGERPRINT,
    GENERIC_COOKIES,
)
from w3af.core.data.constants.dbms import MYSQL
from w3af.core.data.constants.disclaimer import DISCLAIMER
from w3af.core.data.constants.file_extensions import CSS, FLASH, IMAGES, JAVASCRIPT
from w3af.core.data.constants.file_patterns import FILE_PATTERNS
from w3af.core.data.constants.http_messages import W3C_REASONS
from w3af.core.data.constants.ignored_params import (
    IGNORED_PARAMETERS,
    is_in_ignored_parameters,
)
from w3af.core.data.constants.ports import MAILER
from w3af.core.data.constants.response_codes import OK
from w3af.core.data.constants.severity import HIGH
from w3af.core.data.constants.vulns import VULNS
from w3af.core.data.constants.websockets import (
    DEFAULT_PROTOCOL_VERSION,
    WEBSOCKET_UPGRADE_HEADERS,
)


class TestAll(unittest.TestCase):
    def test_simple_constants(self):
        self.assertEqual(MYSQL, "MySQL database")
        self.assertIn("w3af", DISCLAIMER)
        self.assertEqual(MAILER, 25)
        self.assertEqual(OK, 200)
        self.assertEqual(HIGH, "High")
        self.assertIn("PHPSESSID", IGNORED_PARAMETERS)
        self.assertIsNone(VULNS["Manually added vulnerability"])
        self.assertIn("root:x:0:0:", FILE_PATTERNS)

    def test_all_cookies_merges_fingerprints_and_generic_names(self):
        fingerprinted = {name for name, _ in COOKIE_FINGERPRINT}

        self.assertEqual(ALL_COOKIES, fingerprinted | GENERIC_COOKIES)
        self.assertIn("PHPSESSID", ALL_COOKIES)
        self.assertIn("session_id", ALL_COOKIES)

    def test_file_extensions(self):
        self.assertEqual(JAVASCRIPT, {"js"})
        self.assertEqual(CSS, {"css"})
        self.assertEqual(FLASH, {"swf"})
        self.assertIn("png", IMAGES)

    def test_http_messages(self):
        self.assertEqual(W3C_REASONS[404], ["not found"])

    def test_common_words(self):
        self.assertIn("the", common_words["en"])

    def test_websocket_upgrade_headers(self):
        self.assertEqual(
            WEBSOCKET_UPGRADE_HEADERS["Sec-WebSocket-Version"],
            str(DEFAULT_PROTOCOL_VERSION),
        )

    def test_is_in_ignored_parameters_ignores_case(self):
        self.assertTrue(is_in_ignored_parameters("phpsessid"))
        self.assertFalse(is_in_ignored_parameters("username"))
