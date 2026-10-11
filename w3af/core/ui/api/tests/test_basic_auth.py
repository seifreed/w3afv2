"""
test_basic_auth.py

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

import base64

from w3af.core.ui.api.application import app
from w3af.core.ui.api.tests.utils.api_unittest import APIUnitTest


def basic_auth(username, password):
    token = base64.b64encode(f"{username}:{password}".encode()).decode("ascii")
    return {"Authorization": f"Basic {token}"}


class BasicAuthTest(APIUnitTest):
    def test_valid_credentials(self):
        response = self.app.get("/version", headers=self.HEADERS)
        self.assertEqual(response.status_code, 200, response.data)

    def test_missing_credentials_ask_the_browser_for_them(self):
        response = self.app.get("/version")

        self.assertEqual(response.status_code, 401)
        response_json = response.json
        if response_json is None:
            raise AssertionError("Unauthorized response has no JSON body")
        self.assertEqual(response_json["code"], 401)
        self.assertTrue(response.headers["WWW-Authenticate"].startswith("Basic "))

    def test_wrong_credentials(self):
        for headers in (
            basic_auth("admin", "wrong"),
            basic_auth("root", self.PASSWORD),
            basic_auth("ádmin", self.PASSWORD),
            {"Authorization": "Bearer token"},
        ):
            with self.subTest(headers=headers):
                response = self.app.get("/version", headers=headers)
                self.assertEqual(response.status_code, 401)

    def test_other_errors_do_not_ask_for_credentials(self):
        response = self.app.get("/scans/1234/status", headers=self.HEADERS)

        self.assertEqual(response.status_code, 404)
        self.assertNotIn("WWW-Authenticate", response.headers)

    def test_no_password_configured(self):
        app.config.pop("PASSWORD")

        response = self.app.get("/version")

        self.assertEqual(response.status_code, 200, response.data)
