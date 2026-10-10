"""
test_views.py

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

import re
from html.parser import HTMLParser

from w3af.core.ui.api.application import app
from w3af.core.ui.api.tests.utils.api_unittest import APIUnitTest
from w3af.core.ui.web.views import CONTENT_SECURITY_POLICY, blueprint, register

register(app)

API_CALLS = re.compile(r"api\(\s*[`\"]/(?P<resource>[a-z-]+)")


class AssetCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.assets = []
        self.ids = set()
        self.inline_scripts = 0

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if "id" in attributes:
            self.ids.add(attributes["id"])
        if tag == "script" and "src" not in attributes:
            self.inline_scripts += 1
        for name in ("src", "href"):
            if attributes.get(name, "").startswith("static/"):
                self.assets.append(attributes[name])


class WebUITest(APIUnitTest):
    def get(self, path, authenticated=True):
        headers = self.HEADERS if authenticated else None
        return self.app.get(path, headers=headers)

    def index(self):
        response = self.get("/ui/")
        self.assertEqual(response.status_code, 200, response.data)
        collector = AssetCollector()
        collector.feed(response.get_data(as_text=True))
        return response, collector

    def test_index_page(self):
        response, collector = self.index()

        self.assertEqual(response.mimetype, "text/html")
        self.assertEqual(
            response.headers["Content-Security-Policy"], CONTENT_SECURITY_POLICY
        )
        self.assertEqual(response.headers["X-Frame-Options"], "DENY")
        self.assertEqual(response.headers["Referrer-Policy"], "no-referrer")
        self.assertEqual(collector.inline_scripts, 0)
        self.assertIn("scan-form", collector.ids)
        self.assertIn('<meta name="viewport"', response.get_data(as_text=True))

    def test_index_assets_are_served(self):
        _, collector = self.index()

        self.assertEqual(sorted(collector.assets), ["static/app.css", "static/app.js"])
        for asset in collector.assets:
            with self.subTest(asset=asset):
                response = self.get(f"/ui/{asset}")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    response.headers["Content-Security-Policy"],
                    CONTENT_SECURITY_POLICY,
                )
                response.close()

    def test_script_elements_exist_in_page(self):
        _, collector = self.index()
        script = self.get("/ui/static/app.js").get_data(as_text=True)

        referenced_ids = set(re.findall(r'byId\("([a-z-]+)"\)', script))

        self.assertTrue(referenced_ids)
        self.assertEqual(referenced_ids - collector.ids, set())

    def test_script_uses_existing_api_resources(self):
        script = self.get("/ui/static/app.js").get_data(as_text=True)
        rules = {rule.rule for rule in app.url_map.iter_rules()}

        resources = {match.group("resource") for match in API_CALLS.finditer(script)}

        self.assertEqual(resources, {"plugins", "profiles", "scans", "version"})
        for resource in resources:
            with self.subTest(resource=resource):
                self.assertTrue(any(rule.startswith(f"/{resource}") for rule in rules))

    def test_requires_credentials(self):
        for path in ("/ui/", "/ui/static/app.js"):
            with self.subTest(path=path):
                response = self.get(path, authenticated=False)
                self.assertEqual(response.status_code, 401)
                self.assertIn("WWW-Authenticate", response.headers)

    def test_redirects_to_trailing_slash(self):
        response = self.get("/ui")

        self.assertEqual(response.status_code, 308)
        self.assertTrue(response.headers["Location"].endswith("/ui/"))

    def test_register_is_idempotent(self):
        register(app)

        self.assertIs(app.blueprints[blueprint.name], blueprint)
