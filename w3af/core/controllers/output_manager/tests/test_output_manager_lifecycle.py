"""
test_output_manager_lifecycle.py

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

import multiprocessing
import os
import queue
import subprocess
import sys
import tempfile
import threading
import unittest
from contextlib import redirect_stdout
from io import StringIO

import w3af.core.controllers.output_manager as om
from w3af import ROOT_PATH
from w3af.core.constants import POISON_PILL
from w3af.core.controllers.output_manager import (
    close_default_output_manager,
    create_output_manager,
    fresh_output_manager_inst,
)
from w3af.core.controllers.output_manager.log_sink import LogSink
from w3af.core.controllers.output_manager.manager import OutputManager
from w3af.core.controllers.tests.recording_output import recording_output
from w3af.core.controllers.threads.silent_joinable_queue import SilentJoinableQueue
from w3af.core.data.kb.info import Info
from w3af.core.data.kb.knowledge_base import DBKnowledgeBase
from w3af.plugins.output.console import console

WAIT_SECONDS = 10


class EventfulOutput(recording_output):
    """
    A recording output plugin which also records the calls to flush(), end()
    and log_enabled_plugins(), and which can be configured to fail or block.
    """

    def __init__(self, failure=None):
        recording_output.__init__(self)
        self.failure = failure
        self.flushed = threading.Event()
        self.ended = threading.Event()
        self.release_end = threading.Event()
        self.release_end.set()
        self.enabled_plugins = None

    def information(self, message, new_line=True):
        if self.failure is not None:
            raise self.failure
        recording_output.information(self, message, new_line)

    def flush(self):
        self.flushed.set()
        if self.failure is not None:
            raise self.failure

    def end(self):
        self.ended.set()
        self.release_end.wait(WAIT_SECONDS)
        if self.failure is not None:
            raise self.failure

    def log_enabled_plugins(self, enabled_plugins_dict, plugin_options_dict):
        self.enabled_plugins = (enabled_plugins_dict, plugin_options_dict)


def stop(manager):
    manager.in_queue.put(POISON_PILL)
    manager.join(WAIT_SECONDS)


def information(message):
    return (("information", message), {})


class TestOutputManagerRun(unittest.TestCase):
    def test_create_output_manager_owns_matching_sink(self):
        manager, output = create_output_manager()

        self.addCleanup(manager.stop)
        self.assertIs(output.om_queue, manager.get_in_queue())

    def started_manager(self, *plugins, flush_timeout=OutputManager.FLUSH_TIMEOUT):
        manager = OutputManager(flush_timeout=flush_timeout)
        for plugin in plugins:
            manager.set_output_plugin_inst(plugin)
        manager.start()
        self.addCleanup(manager.join, WAIT_SECONDS)
        return manager

    def test_poison_pill_stops_the_manager(self):
        manager = self.started_manager()
        manager.flush_plugin_output()

        stop(manager)

        self.assertFalse(manager.is_alive())
        self.assertTrue(manager._worker_pool.is_closed())

    def test_stop_is_idempotent(self):
        manager = self.started_manager()
        manager.flush_plugin_output()

        manager.stop()
        manager.stop()

        self.assertFalse(manager.is_alive())
        self.assertTrue(manager._worker_pool.is_closed())
        self.assertTrue(manager.in_queue._closed)
        self.assertTrue(manager.in_queue._joincancelled)

    def test_messages_reach_every_plugin_even_when_one_fails(self):
        failing = EventfulOutput(failure=RuntimeError("information failed"))
        recorder = EventfulOutput()
        manager = self.started_manager(failing, recorder)

        manager.in_queue.put(information("hello"))
        manager.in_queue.join()
        stop(manager)

        self.assertEqual(recorder.messages, [("information", "hello")])
        self.assertEqual(failing.messages, [])

    def test_idle_manager_flushes_plugins_after_timeout(self):
        recorder = EventfulOutput()
        manager = self.started_manager(recorder, flush_timeout=0.05)

        self.assertTrue(recorder.flushed.wait(WAIT_SECONDS))
        stop(manager)

    def test_closed_queue_writer_stops_the_manager(self):
        manager = OutputManager()
        manager.in_queue._writer.close()

        manager.start()
        manager.join(WAIT_SECONDS)

        self.assertFalse(manager.is_alive())

    def test_closed_queue_reader_stops_the_manager(self):
        manager = OutputManager()
        manager.in_queue._reader.close()

        manager.start()
        manager.join(WAIT_SECONDS)

        self.assertFalse(manager.is_alive())

    def test_messages_are_dropped_while_plugins_end(self):
        recorder = EventfulOutput()
        recorder.release_end.clear()
        manager = self.started_manager(recorder)

        ending = threading.Thread(target=manager.end_output_plugins)
        ending.start()
        self.assertTrue(recorder.ended.wait(WAIT_SECONDS))

        manager.in_queue.put(information("dropped"))
        manager.in_queue.join()
        recorder.release_end.set()
        ending.join(WAIT_SECONDS)
        stop(manager)

        self.assertEqual(recorder.messages, [])
        self.assertEqual(manager.get_output_plugin_inst(), [])


class TestOutputManagerFlush(unittest.TestCase):
    def test_flush_skips_plugin_still_flushing(self):
        recorder = EventfulOutput()
        recorder.is_running_flush = True
        manager = OutputManager(flush_timeout=0)
        manager.set_output_plugin_inst(recorder)

        manager.flush_plugin_output()
        manager.end_output_plugins()

        self.assertFalse(recorder.flushed.is_set())

    def test_flush_failure_without_core_is_ignored(self):
        failing = EventfulOutput(failure=RuntimeError("flush failed"))
        manager = OutputManager(flush_timeout=0)
        manager.set_output_plugin_inst(failing)

        manager.flush_plugin_output()
        manager._worker_pool.close()
        manager._worker_pool.join()

        self.assertTrue(failing.flushed.is_set())
        self.assertFalse(failing.is_running_flush)

    def test_flush_after_end_does_nothing(self):
        recorder = EventfulOutput()
        manager = OutputManager(flush_timeout=0)
        manager.end_output_plugins()
        manager.set_output_plugin_inst(recorder)

        manager.flush_plugin_output()

        self.assertFalse(recorder.flushed.is_set())


class TestOutputManagerPlugins(unittest.TestCase):
    def test_replacing_plugins_ends_previous_instances(self):
        previous = EventfulOutput()
        manager = OutputManager()
        manager.set_output_plugin_inst(previous)

        manager.set_output_plugins([])

        self.assertTrue(previous.ended.is_set())

    def test_stop_releases_standalone_plugin_database(self):
        manager = OutputManager()
        plugin = manager._get_plugin_instance("xml_file")
        manager.set_output_plugin_inst(plugin)
        database = manager._standalone_database

        assert database is not None
        manager.stop()

        self.assertIsNone(manager._standalone_database)
        self.assertTrue(database.sql_executor.get_received_poison_pill())

    def test_end_raises_first_plugin_exception_after_ending_all(self):
        first = EventfulOutput(failure=RuntimeError("first"))
        second = EventfulOutput(failure=ValueError("second"))
        manager = OutputManager()
        manager.set_output_plugin_inst(first)
        manager.set_output_plugin_inst(second)

        with self.assertRaises(RuntimeError):
            manager.end_output_plugins()

        self.assertTrue(first.ended.is_set())
        self.assertTrue(second.ended.is_set())

    def test_end_keeps_only_console_plugin(self):
        with tempfile.TemporaryDirectory() as output_dir:
            export_options = self.export_requests_options(output_dir)
            manager = OutputManager()
            manager.set_knowledge_base(kb)
            manager.set_plugin_options("export_requests", export_options)
            manager.set_output_plugins(["console", "export_requests"])

            manager.end_output_plugins()

        self.assertEqual(manager.get_output_plugins(), ["console"])
        (plugin,) = manager.get_output_plugin_inst()
        self.assertIsInstance(plugin, console)

    def export_requests_options(self, output_dir):
        manager = OutputManager()
        manager.set_knowledge_base(kb)
        manager.set_output_plugins(["export_requests"])
        (plugin,) = manager.get_output_plugin_inst()
        options = plugin.get_options()
        options["output_file"].set_value(os.path.join(output_dir, "requests.b64"))
        return options

    def test_plugin_options_are_applied(self):
        options = console().get_options()
        options["verbose"].set_value(True)
        manager = OutputManager()
        manager.set_plugin_options("console", options)

        manager.set_output_plugins(["console"])

        (plugin,) = manager.get_output_plugin_inst()
        self.assertTrue(plugin.verbose)

    def test_console_does_not_allocate_standalone_plugin_database(self):
        manager = OutputManager()

        manager.set_output_plugins(["console"])

        self.assertIsNone(manager._standalone_database)

    def test_all_enables_every_output_plugin(self):
        manager = OutputManager()
        self.addCleanup(manager.stop)

        manager.set_output_plugins(["all"])

        plugin_files = os.listdir(os.path.join(ROOT_PATH, "plugins", "output"))
        expected = {
            os.path.splitext(name)[0]
            for name in plugin_files
            if name.endswith(".py")
            and name != "__init__.py"
            and name not in {"xml_filters.py", "xml_models.py", "xml_nodes.py"}
        }
        names = {plugin.get_name() for plugin in manager.get_output_plugin_inst()}
        self.assertEqual(names, expected)
        self.assertEqual(manager.get_output_plugins(), ["all"])

    def test_log_enabled_plugins_reaches_plugins(self):
        recorder = EventfulOutput()
        manager = OutputManager()
        manager.set_output_plugin_inst(recorder)

        manager.log_enabled_plugins({"audit": ["sqli"]}, {"audit": {}})

        self.assertEqual(recorder.enabled_plugins, ({"audit": ["sqli"]}, {"audit": {}}))


class TestOutputManagerModule(unittest.TestCase):
    def test_close_default_manager_releases_global_resources(self):
        manager = OutputManager()
        manager.start()
        om.manager = manager
        om.out = LogSink(manager.get_in_queue())

        close_default_output_manager()

        self.assertFalse(manager.is_alive())
        self.assertIsNone(om.__dict__.get("_manager"))
        self.assertIsNone(om.__dict__.get("_out"))

    def test_import_does_not_create_default_resources(self):
        code = """
import w3af.core.controllers.output_manager as output_manager
print(
    output_manager.__dict__.get("_manager"),
    output_manager.__dict__.get("_out"),
    "manager" in output_manager.__dict__,
    "out" in output_manager.__dict__,
)
"""
        result = subprocess.run(
            [sys.executable, "-c", code],
            check=True,
            capture_output=True,
            text=True,
            env=os.environ,
        )

        self.assertEqual(result.stdout.strip(), "None None False False")

    def setUp(self):
        self.previous_manager = om.manager
        self.previous_out = om.out
        self.addCleanup(self.restore_globals)

    def restore_globals(self):
        om.manager = self.previous_manager
        om.out = self.previous_out

    def test_fresh_instance_stops_the_running_one(self):
        running = OutputManager()
        running.flush_plugin_output()
        running.start()
        om.manager = running

        fresh = fresh_output_manager_inst()
        stop(fresh)

        self.assertFalse(running.is_alive())
        self.assertTrue(running._worker_pool.is_closed())
        self.assertIsNot(fresh, running)
        self.assertIs(om.manager, fresh)

    def test_decorated_method_starts_the_global_manager(self):
        idle = OutputManager()
        om.manager = idle

        idle.process_all_messages()

        self.assertTrue(idle.is_alive())
        stop(idle)

    def test_decorated_method_works_with_a_finished_manager(self):
        finished = OutputManager()
        finished.start()
        stop(finished)
        om.manager = finished

        finished.process_all_messages()

        self.assertFalse(finished.is_alive())


class TestLogSink(unittest.TestCase):
    def test_report_finding_sends_a_vulnerability_message(self):
        messages = queue.Queue()
        sink = LogSink(messages)
        finding = Info("Name", "Finding description", 1, "plugin_name")

        sink.report_finding(finding)

        args, kwargs = messages.get(timeout=WAIT_SECONDS)
        self.assertEqual(args, ("vulnerability", finding.get_desc()))
        self.assertEqual(kwargs, {"severity": finding.get_severity()})

    def test_closed_queue_loses_the_message(self):
        closed_queue = SilentJoinableQueue(ctx=multiprocessing.get_context())
        closed_queue.close()
        sink = LogSink(closed_queue)

        output = StringIO()
        with redirect_stdout(output):
            sink.debug("lost message")

        self.assertIn("LogSink queue communication lost", output.getvalue())


kb = DBKnowledgeBase()
