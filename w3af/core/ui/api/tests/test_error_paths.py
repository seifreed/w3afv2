"""
test_error_paths.py

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

import json

from w3af.core.controllers.w3af_core import w3afCore
from w3af.core.data.kb.knowledge_base import DBKnowledgeBase
from w3af.core.data.kb.vuln import Vuln
from w3af.core.data.parsers.doc.url import URL
from w3af.core.ui.api.application import app
from w3af.core.ui.api.db.master import SCANS, ScanInfo
from w3af.core.ui.api.resources.error_handlers import error_500_handler
from w3af.core.ui.api.tests.utils.api_unittest import APIUnitTest
from w3af.core.ui.api.utils.log_handler import RESTAPIOutput

MISSING_SCAN_ID = 4242
VULN_URL = "http://127.0.0.1/vulnerable.php"


class APIErrorPathsTest(APIUnitTest):
    """
    Exercise the REST API error paths through the Flask test client, using a
    real ScanInfo/w3afCore registered in the scan database where a scan is
    needed.
    """

    def setUp(self):
        super().setUp()
        kb.cleanup()

    def tearDown(self):
        kb.cleanup()
        super().tearDown()

    def _register_scan(self, with_core=True, with_output=False):
        scan_info = ScanInfo()
        if with_core:
            scan_info.w3af_core = w3afCore(knowledge_base=kb)
            self.addCleanup(scan_info.w3af_core.quit)
        if with_output:
            scan_info.output = RESTAPIOutput()
            self.addCleanup(scan_info.output.cleanup)

        scan_id = len(SCANS)
        SCANS[scan_id] = scan_info
        self.addCleanup(SCANS.pop, scan_id, None)
        return scan_id

    def _get(self, path):
        response = self.app.get(path, headers=self.HEADERS)
        return response.status_code, json.loads(response.data)

    def test_index(self):
        status, data = self._get("/")
        self.assertEqual(status, 200)
        self.assertIn("docs", data)

    def test_not_found_handler(self):
        status, data = self._get("/this/route/does/not/exist")
        self.assertEqual(status, 404)
        self.assertEqual(data, {"code": 404, "message": "Not found"})

    def test_method_not_allowed_handler(self):
        response = self.app.put("/", data="{}", headers=self.HEADERS)
        self.assertEqual(response.status_code, 405)
        self.assertEqual(json.loads(response.data)["code"], 405)

    def test_unhandled_exception_returns_debug_info(self):
        app.testing = False
        app.config["TESTING"] = False
        self.addCleanup(app.config.__setitem__, "TESTING", True)
        self.addCleanup(setattr, app, "testing", True)

        status, data = self._get("/raise-500")

        self.assertEqual(status, 500)
        self.assertEqual(data["exception_type"], "ValueError")
        self.assertEqual(data["message"], "Foo!")
        self.assertEqual(data["function_name"], "raise_500")
        self.assertEqual(data["filename"], "error_handlers.py")

    def test_error_handler_without_active_exception(self):
        # Outside of an exception there is no traceback to inspect: the
        # handler must still answer with a generic 500 payload.
        with app.app_context():
            response = error_500_handler(ValueError("no traceback"))

        data = json.loads(response.data)
        self.assertEqual(response.status_code, 500)
        self.assertEqual(data["message"], "REST API error")
        self.assertEqual(data["exception"], "no traceback")

    def test_missing_scan_is_404_everywhere(self):
        paths = (
            f"/scans/{MISSING_SCAN_ID}/kb/",
            f"/scans/{MISSING_SCAN_ID}/kb/0",
            f"/scans/{MISSING_SCAN_ID}/log",
            f"/scans/{MISSING_SCAN_ID}/exceptions/",
            f"/scans/{MISSING_SCAN_ID}/exceptions/0",
            f"/scans/{MISSING_SCAN_ID}/fuzzable-requests/",
            f"/scans/{MISSING_SCAN_ID}/urls/",
            f"/scans/{MISSING_SCAN_ID}/traffic/1",
        )
        for path in paths:
            with self.subTest(path=path):
                status, _ = self._get(path)
                self.assertEqual(status, 404)

        response = self.app.post(
            f"/scans/{MISSING_SCAN_ID}/exceptions/", data="{}", headers=self.HEADERS
        )
        self.assertEqual(response.status_code, 404)

    def test_unknown_exception_id(self):
        scan_id = self._register_scan()
        status, _ = self._get(f"/scans/{scan_id}/exceptions/99")
        self.assertEqual(status, 404)

    def test_clear_scan_without_core(self):
        scan_id = self._register_scan(with_core=False)
        try:
            response = self.app.delete(f"/scans/{scan_id}", headers=self.HEADERS)
        finally:
            # The shared tearDown stops every registered core, this one has none
            SCANS.pop(scan_id)

        self.assertEqual(response.status_code, 400)

    def test_log_without_output(self):
        scan_id = self._register_scan()
        status, data = self._get(f"/scans/{scan_id}/log")
        self.assertEqual(status, 404)
        self.assertIn("Scan output not found", data["message"])

    def test_log_invalid_pagination(self):
        scan_id = self._register_scan(with_output=True)

        for query in ("page=abc", "id=abc", "page=1&id=1"):
            with self.subTest(query=query):
                status, _ = self._get(f"/scans/{scan_id}/log?{query}")
                self.assertEqual(status, 400)

    def test_kb_details_and_url_filter(self):
        scan_id = self._register_scan()

        vuln = Vuln(
            "SQL injection",
            "A SQL injection was found in the id parameter.",
            "High",
            [1],
            "sqli",
        )
        vuln.set_url(URL(VULN_URL))
        kb.append("sqli", "sqli", vuln)

        status, data = self._get(f"/scans/{scan_id}/kb/")
        self.assertEqual(status, 200)
        self.assertEqual([item["url"] for item in data["items"]], [VULN_URL])

        status, data = self._get(f"/scans/{scan_id}/kb/?url={VULN_URL}")
        self.assertEqual(status, 200)
        self.assertEqual(len(data["items"]), 1)

        status, data = self._get(f"/scans/{scan_id}/kb/0")
        self.assertEqual(status, 200)
        self.assertEqual(data["name"], "SQL injection")
        self.assertEqual(data["traffic_hrefs"], [f"/scans/{scan_id}/traffic/1"])

        status, _ = self._get(f"/scans/{scan_id}/kb/7")
        self.assertEqual(status, 404)


kb = DBKnowledgeBase()
