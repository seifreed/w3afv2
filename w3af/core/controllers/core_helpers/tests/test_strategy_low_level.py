"""
test_strategy_low_level.py

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
import threading
import unittest
from urllib.parse import unquote_plus

from w3af import ROOT_PATH
from w3af.core.controllers.core_helpers.fingerprint_404 import (
    fingerprint_404_singleton,
)
from w3af.core.controllers.core_helpers.strategy import CoreStrategy
from w3af.core.controllers.core_helpers.target_validation import (
    alert_if_target_is_301_all,
    replace_targets_with_redir,
    setup_404_detection,
    verify_target_server_up,
)
from w3af.core.controllers.tests.local_http_server import (
    LocalHTTPServer,
    Reply,
    closed_local_port,
)
from w3af.core.controllers.w3af_core import w3afCore
from w3af.core.data.kb.knowledge_base import kb
from w3af.core.exceptions import ScanMustStopByUserRequest, ScanMustStopException

TLS_HELPERS = os.path.join(ROOT_PATH, "core", "data", "url", "tests", "helpers")
TLS_CERT = os.path.join(TLS_HELPERS, "unittest.crt")
TLS_KEY = os.path.join(TLS_HELPERS, "unittest.key")

SQL_ERROR = (
    "You have an error in your SQL syntax; check the manual that corresponds"
    " to your MySQL server version for the right syntax to use"
)


def static_page(method, path):
    return Reply(body="<html><body>Hello world</body></html>")


def sql_injection_site(method, path):
    """
    Behaves like a page which concatenates the id query string parameter
    into a SQL query without escaping it.
    """
    query = unquote_plus(path.partition("?")[2])

    if "'" in query or '"' in query:
        return Reply(body=f"<html><body>{SQL_ERROR}</body></html>")

    return Reply(body="<html><body>Product details</body></html>")


class RouterFailureError(Exception):
    pass


class TeardownAuditThreadsStrategy(CoreStrategy):
    """
    Records the threads which are alive when the audit consumer teardown is
    started.
    """

    def __init__(self, w3af_core):
        super().__init__(w3af_core, kb)
        self.threads_at_teardown_audit = None

    def _teardown_audit(self, *args, **kwargs):
        self.threads_at_teardown_audit = [t.name for t in threading.enumerate()]
        return super()._teardown_audit(*args, **kwargs)


class FailingRouterStrategy(CoreStrategy):
    """
    The fuzzable request router fails, the strategy must terminate all its
    consumers before raising the exception.
    """

    def __init__(self, w3af_core):
        super().__init__(w3af_core, kb)
        self.terminate_calls = 0

    def _fuzzable_request_router(self, *args, **kwargs):
        raise RouterFailureError()

    def terminate(self):
        self.terminate_calls += 1
        return super().terminate()


class TestStrategy(unittest.TestCase):

    def setUp(self):
        kb.cleanup()
        self.server = None

    def tearDown(self):
        self.close_server()

    def close_server(self):
        if self.server is not None:
            self.server.close()
            self.server = None

    def start_server(self, responder):
        self.server = LocalHTTPServer(responder).start()

    def get_core(self, target_url):
        core = w3afCore()
        self.addCleanup(core.quit)

        target = core.target.get_options()
        target["target"].set_value(target_url)
        core.target.set_options(target)

        core.plugins.set_plugins(["sqli"], "audit")
        core.plugins.init_plugins()

        core.verify_environment()
        core.scan_start_hook()

        return core

    def test_strategy_run(self):
        self.start_server(sql_injection_site)
        core = self.get_core(self.server.url("/where_integer_qs.py?id=1"))

        strategy = TeardownAuditThreadsStrategy(core)
        strategy.start()

        # Now test that those threads are being terminated
        self.assertIsNotNone(strategy.threads_at_teardown_audit)
        self.assertIn("WorkerThread", strategy.threads_at_teardown_audit)

        vulns = kb.get("sqli", "sqli")
        self.assertEqual(len(vulns), 1, vulns)

        # Tell the core that we've finished, this should kill the WorkerThreads
        core.scan_end_hook()
        self.close_server()

        self._assert_thread_names()

    def _assert_thread_names(self):
        """
        Makes sure that the threads which are living in my process are the
        ones that I want.
        """
        thread_names = {t.name for t in threading.enumerate()}

        expected_names = {
            "PoolTaskHandler",
            "PoolResultHandler",
            "PoolWorkerHandler",
            "MainThread",
            "SQLiteExecutor",
            "OutputManager",
            "OutputManagerWorkerThread",
            "QueueFeederThread",
        }

        self.assertNotIn("WorkerThread", thread_names)
        self.assertLessEqual(thread_names, expected_names)

    def test_strategy_exception(self):
        self.start_server(sql_injection_site)
        core = self.get_core(self.server.url("/where_integer_qs.py?id=1"))

        strategy = FailingRouterStrategy(core)

        self.assertRaises(RouterFailureError, strategy.start)

        # Now test that those threads are being terminated
        self.assertGreater(strategy.terminate_calls, 0)

        core.scan_end_hook()
        self.close_server()

        self._assert_thread_names()

    def test_strategy_verify_target_server_up(self):
        core = self.get_core(f"http://127.0.0.1:{closed_local_port()}/")

        strategy = CoreStrategy(core, kb)

        try:
            strategy.start()
        except ScanMustStopException as wmse:
            message = str(wmse)
            self.assertIn("Please verify your target configuration", message)
        else:
            self.assertTrue(False)

    def assert_target_redirect_infos(self, build_location, expected_infos):
        """
        :param build_location: Receives the target port and returns the URL
                               which all the target resources redirect to
        """
        self.start_server(self.redirect_all)
        self.redirect_location = build_location(self.server.port)
        core = self.get_core(self.server.url("/"))

        strategy = CoreStrategy(core, kb)
        strategy.start()

        infos = kb.get("core", "core")
        self.assertEqual(len(infos), expected_infos, infos)

    def redirect_all(self, method, path):
        return Reply(
            status=301, body="301", headers={"Location": self.redirect_location}
        )

    def test_alert_if_target_is_301_all_proto_redir(self):
        """
        Tests that the protocol redirection is detected and reported in
        the kb
        """
        https_server = LocalHTTPServer(
            sql_injection_site, tls_cert_and_key=(TLS_CERT, TLS_KEY)
        ).start()
        self.addCleanup(https_server.close)

        self.assert_target_redirect_infos(lambda port: https_server.url("/"), 1)

    def test_alert_if_target_is_301_all_domain_redir(self):
        """
        Tests that the domain redirection is detected and reported in
        the kb
        """
        self.assert_target_redirect_infos(lambda port: f"http://localhost:{port}/", 1)

    def test_alert_if_target_is_301_all_internal_redir(self):
        """
        Tests that no info is created if the site redirects internally
        """
        self.assert_target_redirect_infos(
            lambda port: f"http://127.0.0.1:{port}/xyz", 0
        )

    def target_request_steps(self, strategy):
        core = strategy._w3af_core
        return {
            "replace_targets_with_redir()": lambda: replace_targets_with_redir(core),
            "alert_if_target_is_301_all()": lambda: alert_if_target_is_301_all(
                core, kb
            ),
            "_setup_404_detection()": lambda: setup_404_detection(core),
        }

    def test_target_request_failure_stops_the_scan(self):
        core = self.get_core(f"http://127.0.0.1:{closed_local_port()}/")
        strategy = CoreStrategy(core, kb)

        for step, step_method in self.target_request_steps(strategy).items():
            with self.subTest(step=step):
                with self.assertRaises(ScanMustStopException) as context:
                    step_method()

                self.assertIn(f"Exception found during {step}", str(context.exception))

    def test_user_stop_while_requesting_targets(self):
        self.start_server(static_page)
        core = self.get_core(self.server.url("/"))
        strategy = CoreStrategy(core, kb)

        core.uri_opener.stop()

        steps = self.target_request_steps(strategy)
        steps["verify_target_server_up()"] = lambda: verify_target_server_up(core)

        for step, step_method in steps.items():
            with self.subTest(step=step):
                self.assertRaises(ScanMustStopByUserRequest, step_method)

    def test_404_detection_without_url_opener_uses_basic_checks(self):
        self.start_server(static_page)
        core = self.get_core(self.server.url("/"))

        fingerprint_404_singleton(cleanup=True)

        setup_404_detection(core)
