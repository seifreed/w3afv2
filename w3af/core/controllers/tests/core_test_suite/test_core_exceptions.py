"""
test_core_exceptions.py

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

import errno
import functools
import threading
import unittest

import w3af.core.data.kb.config as cf
from w3af.core.controllers.misc.factory import factory
from w3af.core.controllers.tests.local_http_server import LocalHTTPServer, Reply
from w3af.core.controllers.tests.recording_output import start_recording_output
from w3af.core.controllers.w3af_core import (
    NO_MEMORY_MSG,
    ThreadingResourceError,
    w3afCore,
)
from w3af.core.data.parsers.doc.url import URL
from w3af.core.exceptions import (
    ScanMustStopByUnknownReasonExc,
    ScanMustStopByUserRequest,
    ScanMustStopException,
)
from w3af.plugins.tests.helper import create_target_option_list


class RemoteTracebackError(Exception):
    """
    An exception which carries the traceback from the thread that raised it
    """

    def __init__(self, message):
        super().__init__(message)
        self.original_traceback_string = "Remote traceback for the test"


def os_error(error_number):
    return functools.partial(OSError, error_number)


def static_page(method, path):
    return Reply(body="<html><body>Hello world</body></html>")


class TestCoreExceptions(unittest.TestCase):
    """
    The scan target is a real HTTP server listening on 127.0.0.1
    """

    PLUGIN = "w3af.core.controllers.tests.exception_raise"

    def setUp(self):
        """
        This is a rather complex setUp since I need to move the
        exception_raise.py plugin to the plugin directory in order to be able
        to run it afterwards.

        In the tearDown method, I'll remove the file.
        """
        self.server = LocalHTTPServer(static_page).start()
        self.w3afcore = w3afCore()
        self.recorder = start_recording_output(self.w3afcore._output_manager)

        target_opts = create_target_option_list(URL(self.server.url("/")))
        self.w3afcore.target.set_options(target_opts)

        plugin_inst = factory(self.PLUGIN)
        plugin_inst.set_url_opener(self.w3afcore.uri_opener)
        plugin_inst.set_worker_pool(self.w3afcore.worker_pool)
        plugin_inst.set_output(self.w3afcore.output)

        self.w3afcore.plugins.plugins["crawl"] = [plugin_inst]
        self.w3afcore.plugins._plugins_names_dict["crawl"] = ["exception_raise"]
        self.exception_plugin = plugin_inst

        # Verify env and start the scan
        self.w3afcore.plugins.initialized = True
        self.w3afcore.verify_environment()

    def tearDown(self):
        self.w3afcore.quit()
        self.server.close()

    def test_stop_on_must_stop_exception(self):
        """
        Verify that the ScanMustStopException stops the scan.
        """
        self.exception_plugin.exception_to_raise = ScanMustStopException

        self.w3afcore.start()

        error = (
            "The following error was detected and could not be"
            " resolved:\nTest exception.\n"
        )
        self.assertIn(error, self.recorder.messages_of("error"))

    def test_stop_unknown_exception(self):
        """
        Verify that the ScanMustStopByUnknownReasonExc stops the scan.
        """
        self.exception_plugin.exception_to_raise = ScanMustStopByUnknownReasonExc
        self.assertRaises(ScanMustStopByUnknownReasonExc, self.w3afcore.start)

    def test_stop_by_user_request(self):
        """
        Verify that the ScanMustStopByUserRequest stops the scan.
        """
        self.exception_plugin.exception_to_raise = ScanMustStopByUserRequest

        self.w3afcore.start()

        message = "Test exception."
        self.assertIn(message, self.recorder.messages_of("information"))

    def stop_on_first_exception(self):
        previous = cf.cf.get("stop_on_first_exception")
        self.addCleanup(cf.cf.save, "stop_on_first_exception", previous)
        cf.cf.save("stop_on_first_exception", True)

    def test_memory_error(self):
        self.exception_plugin.exception_to_raise = MemoryError
        self.w3afcore.start()
        self.assertIn(NO_MEMORY_MSG, self.recorder.messages_of("error"))

    def test_os_error_out_of_memory(self):
        self.exception_plugin.exception_to_raise = os_error(errno.ENOMEM)
        self.w3afcore.start()
        self.assertIn(NO_MEMORY_MSG, self.recorder.messages_of("error"))

    def test_os_error_no_space_left(self):
        self.exception_plugin.exception_to_raise = os_error(errno.ENOSPC)
        self.w3afcore.start()

        errors = " ".join(self.recorder.messages_of("error"))
        self.assertIn("the file system is running low on free space", errors)

    def test_other_os_error_is_raised(self):
        self.exception_plugin.exception_to_raise = os_error(errno.EACCES)

        with self.assertRaises(OSError) as context:
            self.w3afcore.start()

        self.assertEqual(context.exception.errno, errno.EACCES)

    def test_threading_error(self):
        self.stop_on_first_exception()
        self.exception_plugin.exception_to_raise = threading.ThreadError

        with self.assertRaises(ThreadingResourceError) as context:
            self.w3afcore.start()

        message = str(context.exception)
        self.assertIn('A "Test exception." threading error was found.', message)
        self.assertIn("MainThread", message)

    def test_unhandled_exception(self):
        self.stop_on_first_exception()
        self.exception_plugin.exception_to_raise = ValueError

        self.assertRaises(ValueError, self.w3afcore.start)

        errors = " ".join(self.recorder.messages_of("error"))
        self.assertIn('Unhandled exception "Test exception.", traceback:', errors)
        self.assertIn("raise self.exception_to_raise", errors)

    def test_unhandled_exception_with_original_traceback(self):
        self.stop_on_first_exception()
        self.exception_plugin.exception_to_raise = RemoteTracebackError

        self.assertRaises(RemoteTracebackError, self.w3afcore.start)

        errors = " ".join(self.recorder.messages_of("error"))
        self.assertIn("Remote traceback for the test", errors)
