"""
test_plugins.py

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

from w3af.core.ui.api.tests.utils.api_unittest import APIUnitTest


class PluginsTest(APIUnitTest):
    def get(self, path):
        return self.app.get(path, headers=self.HEADERS)

    def test_list_plugin_types(self):
        response = self.get("/plugins/")
        self.assertEqual(response.status_code, 200, response.data)

        items = {item["type"]: item for item in response.json["items"]}
        self.assertEqual(list(items), sorted(items))
        self.assertNotIn("attack", items)
        self.assertIn("sqli", items["audit"]["plugins"])
        self.assertIn("web_spider", items["crawl"]["plugins"])
        self.assertTrue(items["audit"]["description"].startswith("Audit plugins"))

    def test_get_plugin_details(self):
        response = self.get("/plugins/crawl/web_spider")
        self.assertEqual(response.status_code, 200, response.data)

        plugin = response.json
        self.assertEqual(plugin["type"], "crawl")
        self.assertEqual(plugin["name"], "web_spider")
        self.assertTrue(plugin["description"])
        self.assertFalse(plugin["long_description"].startswith(" "))

        options = {option["name"]: option for option in plugin["options"]}
        self.assertEqual(options["only_forward"]["type"], "boolean")
        self.assertEqual(options["only_forward"]["value"], "False")
        self.assertTrue(options["only_forward"]["help"])

    def test_unknown_plugins(self):
        for path in ("/plugins/audit/nope", "/plugins/attack/sqlmap"):
            with self.subTest(path=path):
                response = self.get(path)
                self.assertEqual(response.status_code, 404)
                self.assertEqual(response.json["message"], "Plugin not found")
