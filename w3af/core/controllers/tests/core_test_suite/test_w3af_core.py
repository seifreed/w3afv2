"""
test_w3af_core.py

Copyright 2026 w3af contributors

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

import gc
import os
import shutil
import signal
import socket
import stat
import tempfile
import threading
import unittest

from w3af.core.controllers.core_helpers.runtime_directories import (
    prepare_home_directory,
    prepare_tmp_directory,
)
from w3af.core.controllers.tests.local_http_server import LocalHTTPServer, Reply
from w3af.core.controllers.tests.recording_output import start_recording_output
from w3af.core.controllers.w3af_core import w3afCore
from w3af.core.data.parsers.doc.url import URL
from w3af.core.exceptions import BaseFrameworkException
from w3af.core.filesystem import get_temp_dir
from w3af.plugins.tests.helper import create_target_option_list

HOME_DIR_VARIABLE = "W3AF_HOME_DIR"


def linked_site(method, path):
    return Reply(body='<html><body><a href="/linked">linked</a></body></html>')


class TestW3afCore(unittest.TestCase):

    def setUp(self):
        self.server = LocalHTTPServer(linked_site).start()
        self.addCleanup(self.server.close)

        self.core = w3afCore()
        self.addCleanup(self.core.quit)

    def set_target(self):
        target_opts = create_target_option_list(URL(self.server.url("/")))
        self.core.target.set_options(target_opts)

    def enable_crawl(self):
        self.core.plugins.set_plugins(["web_spider"], "crawl")
        self.core.plugins.init_plugins()

    def assert_environment_error(self, message):
        with self.assertRaises(BaseFrameworkException) as context:
            self.core.verify_environment()

        self.assertIn(message, str(context.exception))

    def test_plugins_must_be_initialized(self):
        self.assert_environment_error("You must call the plugins.init_plugins()")

    def test_configuration_is_local_to_core_instance(self):
        other_core = w3afCore()
        self.addCleanup(other_core.quit)

        self.core.configuration.save("test_value", "first")

        self.assertIsNone(other_core.configuration.get("test_value"))

    def test_knowledge_base_is_local_to_core_instance(self):
        other_core = w3afCore()
        self.addCleanup(other_core.quit)

        self.core.knowledge_base.raw_write("test", "value", "first")

        self.assertEqual(other_core.knowledge_base.raw_read("test", "value"), [])

    def test_quit_stops_output_manager(self):
        self.assertTrue(self.core._output_manager.is_alive())

        self.core.quit()

        self.assertFalse(self.core._output_manager.is_alive())

    def test_unreferenced_core_stops_output_manager(self):
        core = w3afCore()
        core.plugins.set_plugins(["console"], "output")
        core.plugins.init_plugins()
        manager = core._output_manager

        del core
        gc.collect()

        self.assertFalse(manager.is_alive())

    def test_unreferenced_core_stops_parser_workers(self):
        core = w3afCore()
        parser_cache = core.parser_cache
        parser_cache._mp_parser.start_workers()

        del core
        gc.collect()

        self.assertIsNone(parser_cache._mp_parser._pool)

    def test_unreferenced_core_does_not_mutate_dns_resolver(self):
        original = socket.getaddrinfo
        core = w3afCore()

        del core
        gc.collect()

        self.assertIs(socket.getaddrinfo, original)

    def test_target_is_required(self):
        self.core.plugins.initialized = True
        self.assert_environment_error("No target URI configured.")

    def test_plugins_are_required(self):
        self.core.plugins.initialized = True
        self.set_target()
        self.assert_environment_error("No audit, grep or crawl plugins configured")

    def test_start_reports_environment_errors(self):
        recorder = start_recording_output(self.core._output_manager)

        self.assertRaises(BaseFrameworkException, self.core.start)

        errors = " ".join(recorder.messages_of("error"))
        self.assertIn("verify_environment() raised an exception", errors)

    def run_scan(self):
        self.set_target()
        self.enable_crawl()
        self.core.verify_environment()
        self.core.start()

    def test_second_scan_starts_from_a_clean_state(self):
        self.assertFalse(self.core.can_stop())

        self.run_scan()

        self.assertTrue(self.core.can_cleanup())
        self.assertFalse(self.core.can_stop())
        first_scan_urls = {
            u.url_string for u in self.core.knowledge_base.get_all_known_urls()
        }
        self.assertIn(self.server.url("/linked"), first_scan_urls)

        self.core.exception_handler.get_all_exceptions().append("old exception")
        self.run_scan()

        second_scan_urls = {
            u.url_string for u in self.core.knowledge_base.get_all_known_urls()
        }
        self.assertEqual(second_scan_urls, first_scan_urls)
        self.assertEqual(self.core.exception_handler.get_all_exceptions(), [])
        self.assertEqual(self.core.status.scans_completed, 2)
        self.assertIs(self.core.status._consumer_metrics._strategy, self.core.strategy)

    def test_pause_and_resume(self):
        self.core.status.start()

        self.core.pause(True)
        self.assertTrue(self.core.status.is_paused())
        self.assertTrue(self.core.can_stop())

        self.core.pause(False)
        self.assertFalse(self.core.status.is_paused())

    def stop_running_core(self):
        recorder = start_recording_output(self.core._output_manager)
        self.core.STOP_TIMEOUT = 1
        self.core.STOP_LOOP_DELAY = 0.1
        self.core.status.start()

        self.core.stop()

        return " ".join(recorder.messages_of("debug"))

    def test_stop_gives_up_when_the_scan_does_not_stop(self):
        debug = self.stop_running_core()
        self.assertIn("The core failed to stop in 1 seconds, forcing exit.", debug)

    def test_user_cancels_the_stop(self):
        main_thread_id = threading.main_thread().ident
        interrupt = threading.Timer(
            0.3, signal.pthread_kill, args=(main_thread_id, signal.SIGINT)
        )
        interrupt.start()
        self.addCleanup(interrupt.join)

        debug = self.stop_running_core()
        self.assertIn("The user cancelled the cleanup process", debug)


class TestW3afCoreDirectories(unittest.TestCase):

    def setUp(self):
        self.core = w3afCore()
        self.addCleanup(self.core.quit)

        self.work_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.work_dir)

    def use_home_dir(self, home_dir):
        previous = os.environ.get(HOME_DIR_VARIABLE)
        os.environ[HOME_DIR_VARIABLE] = home_dir
        self.addCleanup(self.restore_home_dir, previous)

    @staticmethod
    def restore_home_dir(previous):
        if previous is None:
            os.environ.pop(HOME_DIR_VARIABLE, None)
        else:
            os.environ[HOME_DIR_VARIABLE] = previous

    def test_home_dir_can_not_be_created(self):
        regular_file = os.path.join(self.work_dir, "file")
        with open(regular_file, "w", encoding="utf-8") as handler:
            handler.write("not a directory")

        self.use_home_dir(os.path.join(regular_file, "w3af"))

        with self.assertRaises(SystemExit) as context:
            prepare_home_directory()

        self.assertEqual(context.exception.code, -3)

    def test_home_dir_is_not_writable(self):
        home_dir = os.path.join(self.work_dir, "home")
        for sub_dir in ("webroot", "profiles"):
            os.makedirs(os.path.join(home_dir, sub_dir))

        os.chmod(home_dir, stat.S_IRUSR | stat.S_IXUSR)
        self.addCleanup(os.chmod, home_dir, stat.S_IRWXU)
        self.use_home_dir(home_dir)

        with self.assertRaises(SystemExit) as context:
            prepare_home_directory()

        self.assertEqual(context.exception.code, -3)

    def test_tmp_dir_can_not_be_created(self):
        """
        The temporary directory is replaced by a broken symbolic link, which
        makes its creation fail.
        """
        temp_dir = get_temp_dir()
        moved_temp_dir = os.path.join(self.work_dir, "moved-tmp")
        shutil.move(temp_dir, moved_temp_dir)
        self.addCleanup(shutil.move, moved_temp_dir, temp_dir)

        os.symlink(os.path.join(self.work_dir, "missing"), temp_dir)
        self.addCleanup(os.unlink, temp_dir)

        with self.assertRaises(SystemExit) as context:
            prepare_tmp_directory()

        self.assertEqual(context.exception.code, -3)
