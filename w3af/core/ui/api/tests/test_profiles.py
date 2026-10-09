"""
test_profiles.py

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

from pathlib import Path

from w3af.core.ui.api.tests.utils.api_unittest import APIUnitTest
from w3af.tests.helpers.home_dir import use_temporary_home


class ProfilesTest(APIUnitTest):
    def setUp(self):
        super().setUp()
        self.home = use_temporary_home(self)

    def get(self, path):
        return self.app.get(path, headers=self.HEADERS)

    def compose(self, payload):
        return self.app.post("/profiles/compose", json=payload, headers=self.HEADERS)

    def test_list_profiles_sorted_with_links(self):
        response = self.get("/profiles/")
        self.assertEqual(response.status_code, 200, response.data)

        items = response.json["items"]
        names = [item["name"] for item in items]
        self.assertIn("fast_scan", names)
        self.assertEqual(names, sorted(names, key=str.lower))

        fast_scan = items[names.index("fast_scan")]
        self.assertEqual(fast_scan["href"], "/profiles/fast_scan")
        self.assertTrue(fast_scan["description"].startswith("Perform a fast scan"))

    def test_invalid_profiles_are_not_listed(self):
        self.get("/profiles/")
        broken = Path(self.home, "profiles", "broken.pw3af")
        broken.write_text("[audit.xss]\n", encoding="utf-8")

        names = [item["name"] for item in self.get("/profiles/").json["items"]]
        self.assertNotIn("broken", names)
        self.assertEqual(self.get("/profiles/broken").status_code, 404)

    def test_get_profile_details(self):
        response = self.get("/profiles/fast_scan")
        self.assertEqual(response.status_code, 200, response.data)

        profile = response.json
        self.assertEqual(profile["name"], "fast_scan")
        self.assertIn("[profile]", profile["content"])
        self.assertEqual(sorted(profile["plugins"]["audit"]), ["sqli", "xss"])
        self.assertEqual(profile["plugins"]["mangle"], [])
        self.assertIn("web_spider", profile["plugins"]["crawl"])

    def test_get_unknown_profile(self):
        response = self.get("/profiles/does_not_exist")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json["message"], "Profile not found")

    def test_compose_from_existing_profile(self):
        content = self.get("/profiles/fast_scan").json["content"]

        response = self.compose(
            {"scan_profile": content, "plugins": {"audit": ["os_commanding"]}}
        )
        self.assertEqual(response.status_code, 200, response.data)

        composed = response.json["scan_profile"]
        self.assertIn("[audit.os_commanding]", composed)
        self.assertNotIn("[audit.xss]", composed)
        self.assertIn("[crawl.web_spider]", composed)
        self.assertIn("name = fast_scan", composed)

    def test_compose_without_profile(self):
        response = self.compose({"plugins": {"crawl": ["web_spider"]}})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIn("[profile]", response.json["scan_profile"])
        self.assertIn("[crawl.web_spider]", response.json["scan_profile"])

    def test_compose_rejects_invalid_requests(self):
        invalid_requests = {
            "Expected a JSON object": [],
            "Expected scan_profile to be a string": {"scan_profile": 1, "plugins": {}},
            "Expected plugins to be an object keyed by plugin type": {
                "plugins": ["audit"]
            },
            'Unknown plugin type: "attack"': {"plugins": {"attack": []}},
            'Expected a list of plugin names for "audit"': {
                "plugins": {"audit": "xss"}
            },
            'Unknown plugin: "audit.nope"': {"plugins": {"audit": ["nope"]}},
            'Unknown plugin: "audit.1"': {"plugins": {"audit": [1]}},
        }

        for message, payload in invalid_requests.items():
            with self.subTest(message=message):
                response = self.compose(payload)
                self.assertEqual(response.status_code, 400, response.data)
                self.assertEqual(response.json["message"], message)
