# -*- coding: UTF-8 -*-
"""
test_exception_handler.py

Copyright 2012 Andres Riancho

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
import sys
import threading
import unittest

import pytest

import w3af.core.controllers.output_manager as om
import w3af.core.data.kb.config as cf
from w3af.core.controllers.core_helpers.exception_handler import (
    ExceptionData,
    ExceptionHandler,
)
from w3af.core.controllers.core_helpers.status import CoreStatus
from w3af.core.controllers.w3af_core import w3afCore
from w3af.core.data.dc.generic.kv_container import KeyValueContainer
from w3af.core.data.dc.headers import Headers
from w3af.core.data.misc.serialize import dumps, loads
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.request.fuzzable_request import FuzzableRequest
from w3af.core.exceptions import ScanMustStopException


class TestExceptionHandler(unittest.TestCase):

    EXCEPT_START = 'A "RuntimeError" exception was found'

    def setUp(self):
        self.exception_handler = ExceptionHandler(om.out, cf.cf)
        self.exception_handler.clear()

        self.status = CoreStatus(om.out)
        self.status.set_running_plugin("phase", "plugin")
        self.status.set_current_fuzzable_request("phase", "http://www.w3af.org/")

    def test_get_scan_id_returns_a_memoized_hex_identifier(self):
        scan_id = self.exception_handler.get_scan_id()

        self.assertRegex(scan_id, r"^[0-9a-f]{10}$")
        self.assertEqual(self.exception_handler.get_scan_id(), scan_id)

    def test_handle_exception_data_restores_a_consumer_exception(self):
        try:
            raise ValueError("consumer failure")
        except ValueError as error:
            exception_data = ExceptionData(
                self.status,
                error,
                sys.exc_info()[2],
                "",
                cf.cf,
            )

        self.exception_handler.handle_exception_data(exception_data)

        stored_exception = self.exception_handler.get_all_exceptions()[0]
        self.assertEqual(stored_exception.exception_msg, "consumer failure")
        self.assertEqual(stored_exception.filename, "test_exception_handler.py")

    @pytest.mark.smoke
    def test_handle_one(self):

        try:
            raise RuntimeError("unittest")
        except RuntimeError as e:
            handled_exception = e
            exec_info = sys.exc_info()
            enabled_plugins = ""
            self.exception_handler.handle(self.status, e, exec_info, enabled_plugins)

        scan_id = self.exception_handler.get_scan_id()
        self.assertTrue(scan_id)

        all_edata = self.exception_handler.get_all_exceptions()

        self.assertEqual(1, len(all_edata))

        edata = all_edata[0]

        self.assertTrue(edata.get_summary().startswith(self.EXCEPT_START))
        self.assertTrue("traceback" in edata.get_details())
        self.assertEqual(edata.plugin, "plugin")
        self.assertEqual(edata.phase, "phase")
        self.assertEqual(edata.fuzzable_request, "http://www.w3af.org/")
        self.assertEqual(edata.filename, "test_exception_handler.py")
        self.assertEqual(edata.exception_msg, str(handled_exception))
        self.assertEqual(edata.exception_class, handled_exception.__class__.__name__)
        self.assertGreater(edata.lineno, 0)

    @pytest.mark.smoke
    def test_handle_multiple(self):

        for _ in range(10):
            try:
                raise RuntimeError("unittest")
            except RuntimeError as e:
                exec_info = sys.exc_info()
                enabled_plugins = ""
                self.exception_handler.handle(
                    self.status, e, exec_info, enabled_plugins
                )

        self.exception_handler.get_scan_id()
        all_edata = self.exception_handler.get_all_exceptions()

        self.assertEqual(
            self.exception_handler.MAX_EXCEPTIONS_PER_PLUGIN, len(all_edata)
        )

        edata = all_edata[0]

        self.assertTrue(edata.get_summary().startswith(self.EXCEPT_START))
        self.assertTrue("traceback" in edata.get_details())
        self.assertEqual(edata.plugin, "plugin")
        self.assertEqual(edata.phase, "phase")
        self.assertEqual(edata.fuzzable_request, "http://www.w3af.org/")
        self.assertEqual(edata.filename, "test_exception_handler.py")

    def test_get_unique_exceptions(self):

        for _ in range(10):
            try:
                raise RuntimeError("unittest")
            except RuntimeError as e:
                exec_info = sys.exc_info()
                enabled_plugins = ""
                self.exception_handler.handle(
                    self.status, e, exec_info, enabled_plugins
                )

        all_edata = self.exception_handler.get_all_exceptions()
        self.assertEqual(
            self.exception_handler.MAX_EXCEPTIONS_PER_PLUGIN, len(all_edata)
        )

        unique_edata = self.exception_handler.get_unique_exceptions()
        self.assertEqual(1, len(unique_edata))

        edata = unique_edata[0]

        self.assertTrue(edata.get_summary().startswith(self.EXCEPT_START))
        self.assertTrue("traceback" in edata.get_details())
        self.assertEqual(edata.plugin, "plugin")
        self.assertEqual(edata.phase, "phase")
        self.assertEqual(edata.fuzzable_request, "http://www.w3af.org/")
        self.assertEqual(edata.filename, "test_exception_handler.py")

    def test_get_unique_exceptions_keeps_different_files_at_same_line(self):
        for _ in range(2):
            try:
                raise RuntimeError("unittest")
            except RuntimeError as error:
                self.exception_handler.handle(
                    self.status,
                    error,
                    sys.exc_info(),
                    "",
                )

        exceptions = self.exception_handler.get_all_exceptions()
        exceptions[0].filename = "first.py"
        exceptions[1].filename = "second.py"
        exceptions[1].lineno = exceptions[0].lineno

        self.assertEqual(len(self.exception_handler.get_unique_exceptions()), 2)

    def test_handle_threads_calls(self):

        def test2():
            raise RuntimeError("unittest")

        def test(ehandler):
            try:
                test2()
            except RuntimeError as e:
                exec_info = sys.exc_info()
                enabled_plugins = ""
                ehandler.handle(self.status, e, exec_info, enabled_plugins)

        th = threading.Thread(target=test, args=(self.exception_handler,))
        th.start()
        th.join()

        all_edata = self.exception_handler.get_all_exceptions()

        self.assertEqual(1, len(all_edata))

        edata = all_edata[0]

        self.assertTrue(edata.get_summary().startswith(self.EXCEPT_START))
        self.assertTrue("traceback" in edata.get_details())
        self.assertEqual(edata.plugin, "plugin")
        self.assertEqual(edata.phase, "phase")
        self.assertEqual(edata.fuzzable_request, "http://www.w3af.org/")
        self.assertEqual(edata.filename, "test_exception_handler.py")
        self.assertGreater(edata.lineno, 0)

    def test_handle_multi_calls(self):

        def test3():
            raise RuntimeError("unittest")

        def test2():
            test3()

        def test(ehandler):
            try:
                test2()
            except RuntimeError as e:
                exec_info = sys.exc_info()
                enabled_plugins = ""
                ehandler.handle(self.status, e, exec_info, enabled_plugins)

        test(self.exception_handler)
        all_edata = self.exception_handler.get_all_exceptions()

        self.assertEqual(1, len(all_edata))

        edata = all_edata[0]

        self.assertGreater(edata.lineno, 0)

    def handle_runtime_error(self, message="unittest"):
        try:
            raise RuntimeError(message)
        except RuntimeError as error:
            self.exception_handler.handle(self.status, error, sys.exc_info(), "")

    def test_scan_must_stop_exceptions_are_not_handled(self):
        with self.assertRaises(ScanMustStopException):
            try:
                raise ScanMustStopException("stop")
            except ScanMustStopException as error:
                self.exception_handler.handle(self.status, error, sys.exc_info(), "")

        self.assertEqual(self.exception_handler.get_all_exceptions(), [])

    def test_stop_on_first_exception_raises(self):
        cf.cf.save("stop_on_first_exception", True)
        self.addCleanup(cf.cf.save, "stop_on_first_exception", False)

        with self.assertRaisesRegex(RuntimeError, "first"):
            self.handle_runtime_error("first")

    def test_debug_environment_raises_every_exception(self):
        previous_debug = os.environ.get("DEBUG")
        os.environ["DEBUG"] = "1"
        self.addCleanup(self.restore_debug_environment, previous_debug)

        with self.assertRaisesRegex(RuntimeError, "debugging"):
            self.handle_runtime_error("debugging")

    def restore_debug_environment(self, previous_debug):
        if previous_debug is None:
            os.environ.pop("DEBUG")
        else:
            os.environ["DEBUG"] = previous_debug

    def test_summary_without_exceptions(self):
        summary = self.exception_handler.generate_summary_str()

        self.assertEqual(
            summary,
            "No exceptions were raised during scan with id:"
            f" {self.exception_handler.get_scan_id()}.",
        )

    def test_summary_with_exceptions(self):
        self.handle_runtime_error()
        self.status.set_running_plugin("other_phase", "other_plugin")
        self.handle_runtime_error()
        self.handle_runtime_error()

        summary = self.exception_handler.generate_summary()

        self.assertEqual(summary["total_exceptions"], 3)
        self.assertEqual(sorted(summary["exceptions"]), ["other_phase", "phase"])
        self.assertEqual(len(summary["exceptions"]["other_phase"]), 2)
        plugin, fuzzable_request, exception, traceback_str = summary["exceptions"][
            "phase"
        ][0]
        self.assertEqual(plugin, "plugin")
        self.assertEqual(fuzzable_request, "http://www.w3af.org/")
        self.assertIsInstance(exception, RuntimeError)
        self.assertIn("handle_runtime_error", traceback_str)

        summary_str = self.exception_handler.generate_summary_str()

        self.assertIn("caught 3 exceptions", summary_str)
        self.assertIn("- phase.plugin\n", summary_str)
        self.assertIn("- other_phase.other_plugin\n", summary_str)

    def test_exception_data_string_representations(self):
        self.handle_runtime_error("represent me")

        edata = self.exception_handler.get_all_exceptions()[0]

        self.assertEqual(str(edata), edata.get_details())
        self.assertEqual(edata.get_where(), f"phase.plugin:{edata.lineno}")
        self.assertEqual(
            repr(edata),
            f'<ExceptionData - test_exception_handler.py:{edata.lineno} - "represent me">',
        )


class TestExceptionData(unittest.TestCase):

    def test_requires_exception_instance(self):
        with self.assertRaisesRegex(TypeError, "e must be an Exception"):
            ExceptionData(None, None, None, "", cf.cf)

    def test_requires_core_status_instance(self):
        with self.assertRaisesRegex(
            TypeError,
            "current_status must be a CoreStatus",
        ):
            ExceptionData(None, ValueError(), None, "", cf.cf)

    def get_fuzzable_request(self):
        headers = Headers([("Hello", "World")])
        post_data = KeyValueContainer(init_val=[("a", ["b"])])
        url = URL("http://w3af.org")
        return FuzzableRequest(url, method="GET", post_data=post_data, headers=headers)

    def test_without_traceback(self):
        tb = None
        enabled_plugins = "{}"

        fr = self.get_fuzzable_request()

        core = w3afCore()
        self.addCleanup(core.worker_pool.terminate_join)
        status = CoreStatus(om.out)
        status.set_running_plugin("audit", "sqli", log=False)
        status.set_current_fuzzable_request("audit", fr)

        exception_data = ExceptionData(
            status, KeyError(), tb, enabled_plugins, cf.cf, store_tb=False
        )

        pickled_ed = dumps(exception_data)
        unpickled_ed = loads(pickled_ed)

        self.assertEqual(exception_data.to_json(), unpickled_ed.to_json())

    def test_serialize_deserialize(self):
        try:
            raise KeyError
        except KeyError as e:
            _, _, tb = sys.exc_info()
            enabled_plugins = "{}"

            fr = self.get_fuzzable_request()

            core = w3afCore()
            self.addCleanup(core.worker_pool.terminate_join)
            status = CoreStatus(om.out)
            status.set_running_plugin("audit", "sqli", log=False)
            status.set_current_fuzzable_request("audit", fr)

            exception_data = ExceptionData(
                status, e, tb, enabled_plugins, cf.cf, store_tb=False
            )

            pickled_ed = dumps(exception_data)
            unpickled_ed = loads(pickled_ed)

            self.assertEqual(exception_data.to_json(), unpickled_ed.to_json())

    def test_fail_traceback_serialize(self):
        try:
            raise KeyError
        except KeyError as e:
            _, _, tb = sys.exc_info()
            enabled_plugins = "{}"

            fr = self.get_fuzzable_request()

            core = w3afCore()
            self.addCleanup(core.worker_pool.terminate_join)
            status = CoreStatus(om.out)
            status.set_running_plugin("audit", "sqli", log=False)
            status.set_current_fuzzable_request("audit", fr)

            exception_data = ExceptionData(
                status, e, tb, enabled_plugins, cf.cf, store_tb=True
            )

            self.assertRaises(TypeError, dumps, exception_data)
