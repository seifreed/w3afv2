"""
test_scan.py

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

import base64
import json
from urllib.parse import urlsplit

from w3af.core.ui.api.tests.utils.integration_test import IntegrationTest
from w3af.core.ui.api.tests.utils.test_profile import get_test_profile
from w3af.tests.helpers.sqli_site import SQLInjectionSite


class APIScanTest(IntegrationTest):

    def _start_simple_scan(self):
        site = SQLInjectionSite.serve_for(self)
        target_url = site.url
        profile = get_test_profile(target_url)
        data = {"scan_profile": profile, "target_urls": [target_url]}
        response = self._request(
            "POST",
            f"{self.api_url}/scans/",
            data=json.dumps(data),
            headers=self.headers,
        )

        scan_id = response.json()["id"]
        self.assertEqual(
            response.json(),
            {"message": "Success", "href": f"/scans/{scan_id}", "id": scan_id},
        )
        self.assertEqual(response.status_code, 201)

        #
        # Wait until the scan is in Running state
        #
        response = self.wait_until_running()

        self.assertEqual(response.status_code, 200, response.text)
        list_response = {
            "items": [
                {
                    "href": f"/scans/{scan_id}",
                    "id": scan_id,
                    "status": "Running",
                    "errors": False,
                    "target_urls": [target_url],
                }
            ]
        }
        self.assertEqual(response.json(), list_response)

        #
        # Get the detailed status
        #
        response = self._request("GET", f"{self.api_url}/scans/{scan_id}/status")
        self.assertEqual(response.status_code, 200, response.text)

        json_data = response.json()
        self.assertEqual(json_data["is_running"], True)
        self.assertEqual(json_data["is_paused"], False)
        self.assertEqual(json_data["exception"], None)

        #
        # Wait until the scanner finishes and assert the vulnerabilities
        #
        self.wait_until_finish()

        response = self._request("GET", f"{self.api_url}/scans/{scan_id}/kb/")
        self.assertEqual(response.status_code, 200, response.text)

        vuln_summaries = response.json()["items"]
        names = {v["name"] for v in vuln_summaries}
        urls = {v["url"] for v in vuln_summaries}

        self.assertEqual(len(site.vulnerable_urls()), len(vuln_summaries))
        self.assertEqual(names, {"SQL injection"})
        self.assertEqual(urls, set(site.vulnerable_urls()))

        #
        # Make sure I can access the vulnerability details
        #
        response = self._request("GET", f"{self.api_url}/scans/{scan_id}/kb/0")
        self.assertEqual(response.status_code, 200, response.text)

        vuln_info = response.json()
        self.assertEqual(vuln_info["plugin_name"], "sqli")
        self.assertEqual(vuln_info["href"], f"/scans/{scan_id}/kb/0")
        self.assertEqual(vuln_info["id"], 0)
        self.assertEqual(vuln_info["fix_effort"], 50)
        self.assertEqual(vuln_info["cwe_ids"], ["89"])
        self.assertEqual(vuln_info["severity"], "High")
        self.assertEqual(
            vuln_info["tags"], ["web", "sql", "injection", "database", "error"]
        )

        #
        # Get the HTTP traffic for this vulnerability
        #
        traffic_href = vuln_info["traffic_hrefs"][0]
        response = self._request("GET", f"{self.api_url}{traffic_href}")

        traffic_data = response.json()
        self.assertIn("request", traffic_data)
        self.assertIn("response", traffic_data)

        request = base64.b64decode(traffic_data["request"]).decode("utf-8")
        self.assertIn(urlsplit(vuln_info["url"]).path, request)

        #
        # Get the scan log
        #
        response = self._request("GET", f"{self.api_url}/scans/{scan_id}/log")
        self.assertEqual(response.status_code, 200, response.text)

        log_data = response.json()
        self.assertEqual(len(log_data["entries"]), 200)
        self.assertEqual(log_data["next"], 1)
        self.assertEqual(log_data["next_url"], f"/scans/{scan_id}/log?page=1")

        zero_entry = log_data["entries"][0]
        self.assertEqual(zero_entry["message"], "Called w3afCore.start()")
        self.assertEqual(zero_entry["severity"], None)
        self.assertEqual(zero_entry["type"], "debug")
        self.assertIsNotNone(zero_entry["id"])
        self.assertIsNotNone(zero_entry["time"])

        #
        # Clear the scan results
        #
        response = self._request("DELETE", f"{self.api_url}/scans/{scan_id}")
        self.assertEqual(response.json(), {"message": "Success"})
        response = self._request("GET", f"{self.api_url}/scans/{scan_id}/status")
        self.assertEqual(response.status_code, 404, response.text)

        return scan_id

    def test_start_simple_scan(self):
        self._start_simple_scan()

    def test_stop(self):
        site = SQLInjectionSite.serve_for(self, hold_requests=True)
        target_url = site.url
        profile = get_test_profile(target_url)
        data = {"scan_profile": profile, "target_urls": [target_url]}
        response = self._request(
            "POST",
            f"{self.api_url}/scans/",
            data=json.dumps(data),
            headers=self.headers,
        )

        self.assertEqual(
            response.json(), {"message": "Success", "href": "/scans/0", "id": 0}
        )
        self.assertEqual(response.status_code, 201)

        #
        # Wait until the scan is in Running state
        #
        self.wait_until_running()

        #
        # Now stop the scan
        #
        response = self._request("GET", f"{self.api_url}/scans/0/stop")
        self.assertEqual(response.json(), {"message": "Stopping scan"})
        site.release()

        # Wait for it...
        self.wait_until_finish()

        # Assert that we identify the logs associated with stopping the core
        response = self._request("GET", f"{self.api_url}/scans/0/log")
        self.assertEqual(response.status_code, 200, response.text)

        log_data = response.json()["entries"]
        for entry in log_data:
            if "The user stopped the scan" in entry["message"]:
                break
        else:
            self.assertTrue(False, "Stop not found in log")

    def test_two_scans(self):
        scan_id_0 = self._start_simple_scan()
        scan_id_1 = self._start_simple_scan()

        self.assertEqual(scan_id_0, 0)
        self.assertEqual(scan_id_1, 1)
