"""
test_audit.py

Copyright 2018 Andres Riancho

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
import unittest

import w3af.core.controllers.output_manager as om
from w3af.core.controllers.core_helpers.consumers.audit import audit
from w3af.core.controllers.core_helpers.consumers.tests.consumer_plugins import (
    CrashingObserver,
    crashing_audit,
    prepare_plugins,
    recording_audit,
    reported_errors,
)
from w3af.core.controllers.tests.local_http_server import LocalHTTPServer, Reply
from w3af.core.controllers.tests.recording_output import start_recording_output
from w3af.core.controllers.w3af_core import w3afCore
from w3af.core.data.kb.config import Config
from w3af.core.data.kb.knowledge_base import DBKnowledgeBase
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.request.fuzzable_request import FuzzableRequest
from w3af.core.exceptions import ScanMustStopException
from w3af.plugins.audit.xss import xss


def hello_world(method, path):
    return Reply(body="hello world")


class TestAuditConsumer(unittest.TestCase):
    def setUp(self):
        self.server = LocalHTTPServer(hello_world).start()

    def tearDown(self):
        self.server.close()
        kb.cleanup()

    def test_teardown_with_must_stop_exception(self):
        w3af_core = w3afCore(knowledge_base=kb, configuration=cf)
        recorder = start_recording_output()

        xss_instance = xss()
        xss_instance.set_output(om.out)
        xss_instance.set_url_opener(w3af_core.uri_opener)
        xss_instance.set_worker_pool(w3af_core.worker_pool)
        xss_instance.set_knowledge_base(w3af_core.knowledge_base)

        audit_plugins = [xss_instance]
        audit_consumer = audit(
            audit_plugins, w3af_core, om.out, w3af_core.configuration
        )
        audit_consumer.start()

        fr = FuzzableRequest(URL(self.server.url("/?id=1")))

        # This will trigger a few HTTP requests to the target URL which will
        # also initialize all the xss plugin internals to be able to run end()
        # later.
        audit_consumer.in_queue_put(fr)
        kb.add_fuzzable_request(fr)

        # Now that xss.audit() was called, we want to simulate network errors
        # that will put the uri opener in a state where it always answers with
        # ScanMustStopException
        w3af_core.uri_opener._stop_exception = ScanMustStopException("stop")

        # And now we just call terminate() which injects the poison pill and will
        # call teardown, which should call xss.end(), which should try to send HTTP
        # requests, which will raise a ScanMustStopException
        audit_consumer.terminate()

        expected = re.compile(
            r"Spent \d+\.\d\d seconds running xss\.end\(\) until a scan must"
            r" stop exception was raised"
        )
        debug_messages = recorder.messages_of("debug")
        self.assertTrue(
            any(expected.match(message) for message in debug_messages),
            debug_messages,
        )

        w3af_core.worker_pool.terminate_join()


class TestAuditConsumerBranches(unittest.TestCase):
    def setUp(self):
        self.server = LocalHTTPServer(hello_world).start()
        self.addCleanup(self.server.close)
        self.core = w3afCore(knowledge_base=kb, configuration=cf)
        self.addCleanup(self.core.worker_pool.terminate_join)
        self.addCleanup(kb.cleanup)
        self.recorder = start_recording_output()

    def run_audit(self, plugins, urls, observer=None):
        consumer = audit(
            prepare_plugins(plugins, self.core),
            self.core,
            om.out,
            self.core.configuration,
        )
        if observer is not None:
            consumer.add_observer(observer)
        consumer.start()

        for url in urls:
            consumer.in_queue_put(FuzzableRequest(URL(url)))

        consumer.join()
        return consumer

    def test_plugins_receive_the_original_response(self):
        plugin = recording_audit()
        url = self.server.url("/?id=1")

        self.run_audit([plugin], [url])

        self.assertEqual(plugin.audited, [(url, 200)])
        self.assertEqual(plugin.end_calls, 1)
        expected = re.compile(
            r"Spent \d+\.\d\d seconds running recording_audit\.end\(\)$"
        )
        debug_messages = self.recorder.messages_of("debug")
        self.assertTrue(any(expected.match(m) for m in debug_messages))

    def test_plugin_errors_are_reported(self):
        consumer = self.run_audit([crashing_audit()], [self.server.url("/")])

        self.assertEqual(
            reported_errors(consumer),
            [
                ("crashing_audit", "audit failed"),
                ("crashing_audit", "audit end failed"),
            ],
        )

    def test_blacklisted_url_is_not_audited(self):
        url = self.server.url("/blacklisted")
        cf.save("blacklist_audit", [URL(url)])
        self.addCleanup(cf.save, "blacklist_audit", [])
        plugin = recording_audit()

        self.run_audit([plugin], [url])

        self.assertEqual(plugin.audited, [])
        self.assertIn(
            f"{url} was included in the audit blacklist, the scan engine is NOT"
            " going to perform fuzzing on this URL",
            self.recorder.messages_of("debug"),
        )

    def test_original_response_error_is_reported(self):
        plugin = recording_audit()
        self.core.uri_opener.stop()

        consumer = self.run_audit([plugin], [self.server.url("/")])

        self.assertEqual(plugin.audited, [])
        self.assertEqual(
            reported_errors(consumer),
            [("audit.get_original_response()", "The user stopped the scan.")],
        )

    def test_observer_errors_are_reported(self):
        plugin = recording_audit()
        url = self.server.url("/")

        consumer = self.run_audit([plugin], [url], observer=CrashingObserver())

        self.assertEqual(plugin.audited, [(url, 200)])
        self.assertEqual(
            reported_errors(consumer),
            [("audit._run_observers()", "audit observer failed")],
        )


cf = Config()


kb = DBKnowledgeBase()
