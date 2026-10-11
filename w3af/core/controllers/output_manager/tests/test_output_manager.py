"""
test_output_manager.py

Copyright 2011 Andres Riancho

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

import multiprocessing
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO

import pytest
from tblib.decorators import Error

import w3af.core.controllers.output_manager as om
from w3af.core.controllers.output_manager import log_sink_factory
from w3af.core.controllers.threads.decorators import apply_with_return_error
from w3af.core.controllers.w3af_core import w3afCore
from w3af.plugins.output.console import console
from w3af.plugins.output.text_file import text_file


def send_log_message(msg):
    om.out.information(msg)


@pytest.mark.smoke
class TestOutputManager(unittest.TestCase):

    OUTPUT_PLUGIN_ACTIONS = (
        "debug",
        "information",
        "error",
        "console",
        "vulnerability",
    )

    def setUp(self):
        manager = om.manager
        output = om.out
        if (
            not manager.is_alive()
            or output._closed
            or output.om_queue is not manager.get_in_queue()
        ):
            manager = om.fresh_output_manager_inst()
            output = log_sink_factory(manager.get_in_queue())

        self.plugin = console()
        self.plugin.verbose = True
        self.plugin.use_colors = False
        manager._output_plugin_instances = [self.plugin]

    def _run_output_action(self, action, message, new_line=True, **kwargs):
        output = StringIO()
        with redirect_stdout(output):
            getattr(om.out, action)(message, new_line, **kwargs)
            om.manager.process_all_messages()
        return output.getvalue()

    def test_output_plugins_actions(self):
        message = "<< SOME OUTPUT MESS@GE!! <<"
        output = StringIO()
        with redirect_stdout(output):
            for action in self.OUTPUT_PLUGIN_ACTIONS:
                getattr(om.out, action)(message)
            om.manager.process_all_messages()
        self.assertEqual(output.getvalue().count(message + "\r\n"), 5)

    def test_output_plugins_actions_with_unicode_message(self):
        message = "<< ÑñçÇyruZZ!! <<"
        output = StringIO()
        with redirect_stdout(output):
            for action in self.OUTPUT_PLUGIN_ACTIONS:
                getattr(om.out, action)(message)
            om.manager.process_all_messages()
        self.assertEqual(output.getvalue().count(message + "\r\n"), 5)

    def test_method_that_not_exists(self):
        """The output manager implements __getattr__ and we don't want it to
        catch-all, just the ones I define!"""
        with self.assertRaises(AttributeError):
            om.out.foobar("abc")

    def test_kwds(self):
        """The output manager implements __getattr__ with some added
        functools.partial magic. This verifies that it works well with kwds"""
        msg = "foo bar spam eggs"
        action = "information"

        self.assertEqual(self._run_output_action(action, msg, False).count(msg), 1)

    def test_ignore_plugins(self):
        """The output manager implements ignore_plugins to avoid sending a
        message to a specific plugin. Test this feature."""
        msg = "foo bar spam eggs"

        output = StringIO()
        with redirect_stdout(output):
            om.out.information(msg, False, ignore_plugins={self.plugin.get_name()})
            om.out.information(msg, False)
            om.manager.process_all_messages()
        self.assertEqual(output.getvalue().count(msg), 1)

    def test_text_file_encodes_http_log_at_binary_boundary(self):
        with tempfile.TemporaryDirectory() as output_dir:
            http_log_path = os.path.join(output_dir, "http.log")
            plugin = text_file()
            plugin._output_file_name = os.path.join(output_dir, "output.log")
            plugin._http_file_name = http_log_path
            plugin._init()
            plugin._write_to_http_log("header: café")
            plugin.end()

            with open(http_log_path, "rb") as http_log:
                self.assertEqual(http_log.read(), "header: café".encode())

    def test_error_handling(self):
        w3af_core = w3afCore()
        w3af_core.exception_handler.clear()

        om.manager.set_w3af_core(w3af_core, w3af_core._output)
        try:
            raise RuntimeError("output plugin failure")
        except RuntimeError as exception:
            om.manager._handle_output_plugin_exception(self.plugin, exception)

        exc_list = w3af_core.exception_handler.get_all_exceptions()
        self.assertEqual(len(exc_list), 1, exc_list)

        edata = exc_list[-1]
        self.assertIsInstance(edata.exception, RuntimeError)
        self.assertEqual(str(edata.exception), "output plugin failure")

    def test_output_manager_multiprocessing(self):
        msg = "Sent from a different process"

        om.manager._output_plugin_instances = [self.plugin]

        log_queue = om.manager.get_in_queue()
        output = StringIO()
        with redirect_stdout(output):
            with multiprocessing.Pool(
                1, initializer=log_sink_factory, initargs=(log_queue,)
            ) as pool:
                result = pool.apply(apply_with_return_error, ((send_log_message, msg),))
            om.manager.process_all_messages()
        if isinstance(result, Error):
            result.reraise()

        self.assertEqual(output.getvalue().count(msg + "\r\n"), 1)
