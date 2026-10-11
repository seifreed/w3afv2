"""
test_scan_lifecycle.py

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
import re
import time
from typing import Any

from w3af.core.ui.api.tests.utils.api_unittest import APIUnitTest
from w3af.core.ui.api.tests.utils.local_target import LocalTarget

WAIT_SECONDS = 90
POLL_SECONDS = 0.2
SENT_REQUEST = re.compile(r"^GET \S+ returned HTTP code .*\(id:(?P<id>\d+),")


class ScanLifecycleTest(APIUnitTest):
    """
    Drive a real scan through the REST API endpoints used by the web UI
    """

    def setUp(self):
        super().setUp()
        self.target = LocalTarget()
        self.target.start()

    def tearDown(self):
        self.target.release()
        super().tearDown()
        self.target.close()

    def compose_profile(self, plugins):
        response = self.app.post(
            "/profiles/compose",
            json={"scan_profile": "", "plugins": plugins},
            headers=self.HEADERS,
        )
        self.assertEqual(response.status_code, 200, response.data)
        return self._json_object(response)["scan_profile"]

    def start_scan(self, plugins=None):
        plugins = {"crawl": ["web_spider"]} if plugins is None else plugins
        data = {
            "scan_profile": self.compose_profile(plugins),
            "target_urls": [self.target.url],
        }
        response = self.app.post("/scans/", json=data, headers=self.HEADERS)
        self.assertEqual(response.status_code, 201, response.data)
        return self._json_object(response)["id"]

    def status(self, scan_id):
        response = self.app.get(f"/scans/{scan_id}/status", headers=self.HEADERS)
        self.assertEqual(response.status_code, 200, response.data)
        return self._json_object(response)

    def _json_object(self, response) -> dict[str, Any]:
        data = response.json
        if not isinstance(data, dict):
            raise TypeError("Expected an object JSON response")
        return data

    def wait_for_status(self, scan_id, expected):
        deadline = time.monotonic() + WAIT_SECONDS
        while time.monotonic() < deadline:
            status = self.status(scan_id)
            if status["status"] == expected:
                return status
            time.sleep(POLL_SECONDS)
        self.fail(f"Scan never reached the {expected} status")

    def action(self, scan_id, name):
        return self.app.get(f"/scans/{scan_id}/{name}", headers=self.HEADERS)

    def test_pause_resume_stop_and_clear(self):
        scan_id = self.start_scan()
        self.assertTrue(self.target.index_served.wait(WAIT_SECONDS))
        self.wait_for_status(scan_id, "Running")

        self.assertEqual(self.action(scan_id, "resume").status_code, 403)
        self.assertEqual(self.list_scans(), [(scan_id, "Running", [self.target.url])])
        self.assert_rejected(
            {"scan_profile": "", "target_urls": [self.target.url]},
            "concurrent scans",
        )

        self.assertEqual(self.action(scan_id, "pause").status_code, 200)
        self.assertTrue(self.wait_for_status(scan_id, "Paused")["is_paused"])
        self.assertEqual(self.action(scan_id, "pause").status_code, 403)

        self.assertEqual(self.action(scan_id, "resume").status_code, 200)
        self.assertFalse(self.wait_for_status(scan_id, "Running")["is_paused"])

        response = self.app.delete(f"/scans/{scan_id}", headers=self.HEADERS)
        self.assertEqual(response.status_code, 403)

        self.assertEqual(self.action(scan_id, "stop").status_code, 200)
        self.target.release()
        self.wait_for_status(scan_id, "Stopped")

        self.assertEqual(self.action(scan_id, "stop").status_code, 403)
        self.assert_scan_results(scan_id)

        response = self.app.delete(f"/scans/{scan_id}", headers=self.HEADERS)
        self.assertEqual(response.status_code, 200, response.data)

        for name in ("status", "pause", "resume", "stop"):
            self.assertEqual(self.action(scan_id, name).status_code, 404)

        response = self.app.delete(f"/scans/{scan_id}", headers=self.HEADERS)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.list_scans(), [])

    def test_scan_that_fails_to_start(self):
        scan_id = self.start_scan(plugins={})

        status = self.wait_for_status(scan_id, "Stopped")

        self.assertEqual(status["progress"], 0)
        self.assertIn("plugins", status["exception"])
        response = self.app.get("/scans/", headers=self.HEADERS)
        self.assertTrue(self._json_object(response)["items"][0]["errors"])

        response = self.app.delete(f"/scans/{scan_id}", headers=self.HEADERS)
        self.assertEqual(response.status_code, 200, response.data)

    def test_start_scan_validation(self):
        profile = self.compose_profile({"crawl": ["web_spider"]})
        invalid_requests = [
            ({}, "Expected scan_profile in JSON object"),
            ({"scan_profile": profile}, "Expected target_urls in JSON object"),
            (
                {"scan_profile": "[audit.xss]\n", "target_urls": [self.target.url]},
                "does NOT contain a [profile] section",
            ),
            ({"scan_profile": profile, "target_urls": []}, "No target URLs specified"),
            ({"scan_profile": profile, "target_urls": ["http://"]}, "Invalid URL"),
            (
                {"scan_profile": profile, "target_urls": ["ftp://127.0.0.1/"]},
                "Invalid",
            ),
        ]

        for payload, message in invalid_requests:
            with self.subTest(message=message):
                self.assert_rejected(payload, message)

        self.assertEqual(self.list_scans(), [])

    def test_unknown_traffic_id(self):
        scan_id = self.start_scan(plugins={})
        self.wait_for_status(scan_id, "Stopped")

        response = self.app.get(f"/scans/{scan_id}/traffic/99999", headers=self.HEADERS)
        self.assertEqual(response.status_code, 404)

        response = self.app.get("/scans/99/traffic/1", headers=self.HEADERS)
        self.assertEqual(response.status_code, 404)

    def test_exceptions_and_findings_details(self):
        scan_id = self.start_scan(plugins={})
        self.wait_for_status(scan_id, "Stopped")

        response = self.app.post(
            f"/scans/{scan_id}/exceptions/", json={}, headers=self.HEADERS
        )
        self.assertEqual(response.status_code, 201, response.data)

        response = self.app.get(f"/scans/{scan_id}/exceptions/", headers=self.HEADERS)
        items = self._json_object(response)["items"]
        self.assertEqual(len(items), 1)
        self.assertNotIn("traceback", items[0])

        response = self.app.get(items[0]["href"], headers=self.HEADERS)
        self.assertEqual(response.status_code, 200, response.data)
        response_json = self._json_object(response)
        self.assertEqual(response_json["exception"], "unittest")
        self.assertIn("exception_creator", response_json["traceback"])

        response = self.app.get(f"/scans/{scan_id}/kb/0", headers=self.HEADERS)
        self.assertEqual(response.status_code, 404)

    def assert_rejected(self, payload, message):
        response = self.app.post("/scans/", json=payload, headers=self.HEADERS)
        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn(message, self._json_object(response)["message"])

    def list_scans(self):
        response = self.app.get("/scans/", headers=self.HEADERS)
        self.assertEqual(response.status_code, 200, response.data)
        return [
            (item["id"], item["status"], item["target_urls"])
            for item in self._json_object(response)["items"]
        ]

    def assert_scan_results(self, scan_id):
        response = self.app.get(f"/scans/{scan_id}/log?id=0", headers=self.HEADERS)
        self.assertEqual(response.status_code, 200, response.data)
        messages = [
            entry["message"] for entry in self._json_object(response)["entries"]
        ]
        self.assertIn("Called w3afCore.start()", messages)

        request_ids = [
            match.group("id")
            for match in map(SENT_REQUEST.search, messages)
            if match is not None
        ]
        self.assertTrue(request_ids, messages)

        traffic_href = f"/scans/{scan_id}/traffic/{request_ids[0]}"
        response = self.app.get(traffic_href, headers=self.HEADERS)
        self.assertEqual(response.status_code, 200, response.data)
        response_json = self._json_object(response)
        request = base64.b64decode(response_json["request"]).decode()
        response_text = base64.b64decode(response_json["response"]).decode()
        self.assertTrue(request.startswith("GET "), request)
        self.assertIn("w3af</body>", response_text)

        for resource in ("kb/", "urls/", "exceptions/"):
            response = self.app.get(
                f"/scans/{scan_id}/{resource}", headers=self.HEADERS
            )
            self.assertEqual(response.status_code, 200, response.data)
            self.assertIsInstance(self._json_object(response)["items"], list)
