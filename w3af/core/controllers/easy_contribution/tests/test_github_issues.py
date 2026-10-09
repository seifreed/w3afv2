"""
test_github_issues.py

Copyright 2013 Andres Riancho

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
import unittest

from w3af.core.controllers.easy_contribution.github_issues import (
    GITHUB_CREDENTIAL_ENV_VAR,
    get_oauth_token,
)


class TestGetOAuthToken(unittest.TestCase):
    def setUp(self):
        self._saved = os.environ.pop(GITHUB_CREDENTIAL_ENV_VAR, None)

    def tearDown(self):
        os.environ.pop(GITHUB_CREDENTIAL_ENV_VAR, None)
        if self._saved is not None:
            os.environ[GITHUB_CREDENTIAL_ENV_VAR] = self._saved

    def test_no_token_configured(self):
        self.assertIsNone(get_oauth_token())

    def test_empty_token_is_not_configured(self):
        os.environ[GITHUB_CREDENTIAL_ENV_VAR] = ""
        self.assertIsNone(get_oauth_token())

    def test_token_from_environment(self):
        os.environ[GITHUB_CREDENTIAL_ENV_VAR] = "configured-token"
        self.assertEqual(get_oauth_token(), "configured-token")
