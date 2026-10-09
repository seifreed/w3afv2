"""
test_audit_plugin.py

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

from w3af.core.controllers.exceptions import FourOhFourDetectionException
from w3af.core.controllers.plugins.audit_plugin import AuditPlugin
from w3af.core.controllers.tests.recording_output import start_recording_output
from w3af.core.controllers.w3af_core import w3afCore
from w3af.core.data.constants import severity
from w3af.core.data.dc.urlencoded_form import URLEncodedForm
from w3af.core.data.fuzzer.mutants.querystring_mutant import QSMutant
from w3af.core.data.kb.knowledge_base import kb
from w3af.core.data.kb.vuln import Vuln
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.parsers.utils.form_params import FormParameters
from w3af.core.data.request.fuzzable_request import FuzzableRequest
from w3af.core.data.url.extended_urllib import ExtendedUrllib
from w3af.core.data.url.tests.helpers.raw_handlers import TimeoutTCPHandler
from w3af.core.data.url.tests.helpers.upper_daemon import UpperDaemon
from w3af.plugins.audit.sqli import sqli
from w3af.tests.helpers.sqli_site import INTEGER_FORM, STRING_QS, SQLInjectionSite


class TestAuditPlugin(unittest.TestCase):

    def setUp(self):
        kb.cleanup()
        self.w3af = w3afCore()

    def tearDown(self):
        self.w3af.quit()
        kb.cleanup()

    def test_audit_return_vulns(self):
        plugin_inst = self.w3af.plugins.get_plugin_inst("audit", "sqli")

        site = SQLInjectionSite.serve_for(self)
        target_url = site.url + STRING_QS
        uri = URL(target_url + "?uname=pablo")
        freq = FuzzableRequest(uri)

        vulns = plugin_inst.audit_return_vulns(freq)

        self.assertEqual(len(vulns), 1, vulns)

        vuln = vulns[0]
        self.assertEqual("You have an error in your SQL syntax;", vuln["error"])
        self.assertEqual("MySQL database", vuln["db"])
        self.assertEqual(target_url, str(vuln.get_url()))

        self.assertEqual(plugin_inst._store_kb_vulns, False)

    def test_http_timeout_with_plugin(self):
        """
        This is very related with the tests at:
            w3af/core/data/url/tests/test_xurllib.py

        Very similar test is TestXUrllib.test_timeout

        :see: https://github.com/andresriancho/w3af/issues/7112
        """
        upper_daemon = UpperDaemon(TimeoutTCPHandler)
        upper_daemon.start()
        upper_daemon.wait_for_start()

        port = upper_daemon.get_port()

        url = URL(f"http://127.0.0.1:{port}/")
        freq = FuzzableRequest(url)

        plugin_inst = self.w3af.plugins.get_plugin_inst("audit", "sqli")
        plugin_inst._uri_opener.settings.set_configured_timeout(1)
        plugin_inst._uri_opener.clear_timeout()

        # We expect the server to timeout and the response to be a 204
        resp = plugin_inst.get_original_response(freq)
        self.assertEqual(resp.get_url(), url)
        self.assertEqual(resp.get_code(), 204)

        plugin_inst._uri_opener.settings.set_default_values()

    def test_original_response_fills_a_copy_of_the_form(self):
        site = SQLInjectionSite.serve_for(self)
        form_params = FormParameters()
        form_params.set_method("POST")
        form_params.set_action(URL(site.url + INTEGER_FORM))
        form_params.add_field_by_attr_items([("name", "text"), ("type", "text")])
        freq = FuzzableRequest.from_form(URLEncodedForm(form_params))
        plugin_inst = self.w3af.plugins.get_plugin_inst("audit", "sqli")

        resp = plugin_inst.get_original_response(freq)

        self.assertEqual(freq.get_raw_data()["text"], [""])
        self.assertIn("Results for Hello World", resp.get_body())

    def test_audit_return_vulns_logs_errors(self):
        recorder = start_recording_output()
        freq = FuzzableRequest(URL("http://127.0.0.1/"))

        self.assertEqual(sqli().audit_return_vulns(freq), [])
        self.assertIn("send_mutant", recorder.messages_of("error")[0])


def new_vuln(mutant):
    return Vuln.from_mutant(
        "Finding",
        "Found while running a unit test",
        severity.LOW,
        [1],
        "appends_vulns",
        mutant,
    )


def qs_mutant(url="http://127.0.0.1/?id=1"):
    freq = FuzzableRequest(URL(url))
    return QSMutant.create_mutants(freq, ["x"], [], False, {})[0]


class appends_vulns(AuditPlugin):
    """
    Reports a vulnerability for each audited request.
    """

    def audit(self, freq, orig_resp, debugging_id):
        self.kb_append(self.get_name(), self.get_name(), new_vuln(qs_mutant()))


class detects_404_errors(AuditPlugin):
    """
    Fails while detecting 404 pages.
    """

    def audit(self, freq, orig_resp, debugging_id):
        raise FourOhFourDetectionException("404 detection failed")


class TestAuditPluginBase(unittest.TestCase):
    def setUp(self):
        kb.cleanup()
        self.addCleanup(kb.cleanup)
        self.freq = FuzzableRequest(URL("http://127.0.0.1/"))

    def test_kb_append_outside_audit_return_vulns(self):
        plugin = appends_vulns()
        start_recording_output()

        plugin.audit_with_copy(self.freq, None, "did")

        self.assertEqual(len(kb.get("appends_vulns", "appends_vulns")), 1)
        self.assertEqual(plugin._newly_found_vulns, [])

    def test_kb_append_while_returning_vulns(self):
        plugin = appends_vulns()
        start_recording_output()
        plugin._store_kb_vulns = True

        plugin.audit_with_copy(self.freq, None, "did")

        self.assertEqual(plugin._newly_found_vulns, [])
        self.assertFalse(plugin._audit_return_vulns_in_caller())

    def test_audit_return_vulns_collects_kb_append(self):
        site = SQLInjectionSite.serve_for(self)
        uri_opener = ExtendedUrllib()
        self.addCleanup(uri_opener.end)
        plugin = appends_vulns()
        plugin.set_url_opener(uri_opener)
        start_recording_output()

        vulns = plugin.audit_return_vulns(FuzzableRequest(URL(site.url)))

        self.assertEqual([v.get_name() for v in vulns], ["Finding"])
        self.assertEqual(plugin._newly_found_vulns, [])

    def test_404_detection_errors_are_logged(self):
        recorder = start_recording_output()

        self.assertIsNone(detects_404_errors().audit_with_copy(self.freq, None, "d"))
        self.assertIn("404 detection failed", recorder.messages_of("debug"))

    def test_audit_must_be_implemented(self):
        self.assertRaises(
            NotImplementedError, AuditPlugin().audit, self.freq, None, "did"
        )

    def test_has_bug(self):
        plugin = appends_vulns()
        mutant = qs_mutant()
        start_recording_output()

        self.assertFalse(plugin._has_bug(mutant))

        plugin.audit_with_copy(self.freq, None, "did")

        self.assertTrue(plugin._has_bug(mutant))
        self.assertFalse(plugin._has_bug(qs_mutant("http://127.0.0.1/other?id=1")))
        self.assertFalse(plugin._has_bug(mutant, pname="sqli"))

    def test_type(self):
        self.assertEqual(AuditPlugin().get_type(), "audit")
