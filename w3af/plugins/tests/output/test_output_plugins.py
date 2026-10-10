"""
test_output_plugins.py

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

import contextlib
import errno
import io
import os
import shutil
import socket
import tempfile
import unittest
from pathlib import Path

import w3af.core.controllers.output_manager as om
import w3af.core.data.kb.knowledge_base as kb
from w3af.core.data.constants import severity
from w3af.core.data.dc.headers import Headers
from w3af.core.data.kb.config import Config
from w3af.core.data.kb.info import Info
from w3af.core.data.kb.info_set import InfoSet
from w3af.core.data.kb.vuln import Vuln
from w3af.core.data.options.output_file_option import DEV_NULL
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.url.http_request import HTTPRequest
from w3af.core.data.url.http_response import HTTPResponse
from w3af.core.exceptions import BaseFrameworkException, ScanMustStopByKnownReasonExc
from w3af.core.filesystem import create_temp_dir
from w3af.plugins import output
from w3af.plugins.output.console import catch_ioerror, console
from w3af.plugins.output.csv_file import csv_file
from w3af.plugins.output.email_report import email_report
from w3af.plugins.output.export_requests import export_requests
from w3af.plugins.output.html_file import (
    get_severity_icon,
    html_file,
    request_dump,
    response_dump,
)
from w3af.plugins.output.json_file import json_file
from w3af.plugins.output.system_log import system_log
from w3af.plugins.output.text_file import text_file
from w3af.plugins.tests.output.smtp_server import LocalSMTPServer

TARGET = URL("http://www.w3af.com/")
VULN_DESC = "A vulnerability was identified in the application under test"


def _save_config(test_case, name, value):
    test_case.addCleanup(cf.save, name, cf.get(name))
    cf.save(name, value)


def _temp_dir(test_case):
    directory = tempfile.mkdtemp()
    test_case.addCleanup(shutil.rmtree, directory, True)
    return directory


def _closed_port():
    """
    :return: A local TCP port where nothing is listening
    """
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class TestOutputPackage(unittest.TestCase):
    def test_long_description(self):
        self.assertIn("Output plugins", output.get_long_description())


class TestConsole(unittest.TestCase):

    def setUp(self):
        self.plugin = console()

    def _capture(self, method, *args, **kwargs):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            method(*args, **kwargs)
        return stdout.getvalue()

    def test_information_without_colors(self):
        self.plugin.use_colors = False
        written = self._capture(self.plugin.information, "hello\x07 world")
        self.assertEqual(written, "hello world\r\n")

    def test_information_without_newline(self):
        written = self._capture(self.plugin.information, "hello", new_line=False)
        self.assertEqual(written, "hello")

    def test_multiline_messages_add_carriage_returns(self):
        self.plugin.use_colors = False
        written = self._capture(self.plugin.console, "one\ntwo")
        self.assertEqual(written, "one\n\rtwo\r\n")

    def _force_colors(self):
        # termcolor only emits ANSI codes for terminals unless FORCE_COLOR is set
        previous = os.environ.get("FORCE_COLOR")
        os.environ["FORCE_COLOR"] = "1"
        if previous is None:
            self.addCleanup(os.environ.pop, "FORCE_COLOR", None)
        else:
            self.addCleanup(os.environ.__setitem__, "FORCE_COLOR", previous)

    def test_vulnerability_is_colored(self):
        self._force_colors()
        written = self._capture(
            self.plugin.vulnerability, "bad", severity=severity.HIGH
        )
        self.assertIn("\x1b[31m", written)

    def test_error_is_colored(self):
        self._force_colors()
        written = self._capture(self.plugin.error, "failure")
        self.assertIn("failure", written)
        self.assertIn("\x1b[", written)

    def test_debug_requires_verbose(self):
        self.assertEqual(self._capture(self.plugin.debug, "dbg"), "")

        self.plugin.verbose = True
        self.assertIn("dbg", self._capture(self.plugin.debug, "dbg"))

    def test_options_round_trip(self):
        options = self.plugin.get_options()
        options["verbose"].set_value(True)
        options["use_colors"].set_value(False)
        self.plugin.set_options(options)

        self.assertTrue(self.plugin.verbose)
        self.assertFalse(self.plugin.use_colors)

    def test_long_desc(self):
        self.assertIn("console", self.plugin.get_long_desc())

    def test_broken_stdout_is_ignored(self):
        read_fd, write_fd = os.pipe()
        os.close(read_fd)

        # Closing the pipe flushes the buffered text again, which also fails
        # with a broken pipe once the reader is gone.
        with (
            contextlib.suppress(BrokenPipeError),
            open(write_fd, "w") as broken,
            contextlib.redirect_stdout(broken),
        ):
            self.assertIsNone(self.plugin.information("lost message"))

    def test_no_space_left_stops_the_scan(self):
        @catch_ioerror
        def write_to_full_disk(plugin):
            raise OSError(errno.ENOSPC, "No space left on device")

        self.assertRaises(ScanMustStopByKnownReasonExc, write_to_full_disk, self.plugin)


class TestSystemLog(unittest.TestCase):

    def setUp(self):
        self.plugin = system_log()

    def test_random_scan_id_when_not_configured(self):
        self.plugin.set_options(self.plugin.get_options())
        self.assertEqual(len(self.plugin.scan_id), 8)

    def test_configured_scan_id_is_used(self):
        options = self.plugin.get_options()
        options["scan_id"].set_value("my-scan")
        options["verbose"].set_value(True)
        self.plugin.set_options(options)

        self.assertEqual(self.plugin._create_message("hi\x00!"), "[my-scan] hi!")

    def test_all_message_types_are_sent_to_syslog(self):
        options = self.plugin.get_options()
        options["scan_id"].set_value("unittest")
        options["verbose"].set_value(True)
        self.plugin.set_options(options)

        for method in (
            self.plugin.debug,
            self.plugin.error,
            self.plugin.log_crash,
            self.plugin.console,
            self.plugin.vulnerability,
            self.plugin.information,
        ):
            with self.subTest(method=method.__name__):
                self.assertIsNone(method("w3af system_log unittest message"))

    def test_debug_requires_verbose(self):
        self.assertIsNone(self.plugin.debug("not sent"))

    def test_long_desc(self):
        self.assertIn("syslog", self.plugin.get_long_desc())


class TestFileExportErrors(unittest.TestCase):
    """
    The file based output plugins must not crash when the output file can not
    be written, they report the error instead.
    """

    def setUp(self):
        create_temp_dir()
        kb.kb.cleanup()
        _save_config(self, "targets", [TARGET])
        _save_config(self, "target_domains", ["www.w3af.com"])
        self.unwritable = _temp_dir(self)

    def tearDown(self):
        kb.kb.cleanup()

    def test_csv_file(self):
        plugin = csv_file()
        plugin.set_knowledge_base(kb.kb)
        plugin.set_configuration(cf)
        plugin.set_output(om.out)
        plugin.output_file = self.unwritable
        plugin.end()
        self.assertTrue(Path(self.unwritable).is_dir())
        self.assertIn("CSV", plugin.get_long_desc())

    def test_export_requests(self):
        plugin = export_requests()
        plugin.set_knowledge_base(kb.kb)
        plugin.set_configuration(cf)
        plugin.set_output(om.out)
        plugin.output_file = self.unwritable
        plugin.end()
        self.assertTrue(Path(self.unwritable).is_dir())
        self.assertIn("HTTP requests", plugin.get_long_desc())

    def test_json_file(self):
        plugin = json_file()
        plugin.set_knowledge_base(kb.kb)
        plugin.set_configuration(cf)
        plugin.set_output(om.out)
        plugin.output_file = self.unwritable
        plugin.end()
        self.assertTrue(Path(self.unwritable).is_dir())
        self.assertIn("JSON", plugin.get_long_desc())


class TestJsonFileFindings(unittest.TestCase):

    def setUp(self):
        create_temp_dir()
        kb.kb.cleanup()
        _save_config(self, "targets", [TARGET])
        _save_config(self, "target_domains", [])
        self.output_file = os.path.join(_temp_dir(self), "report.json")

    def tearDown(self):
        kb.kb.cleanup()

    def test_info_sets_without_raw_description(self):
        info = Info("Interesting header", VULN_DESC, 1, "plugin")
        info.set_url(TARGET)
        kb.kb.append("plugin", "location", InfoSet([info]))

        plugin = json_file()
        plugin.set_knowledge_base(kb.kb)
        plugin.set_configuration(cf)
        plugin.set_output(om.out)
        plugin.output_file = self.output_file
        plugin.end()

        report = Path(self.output_file).read_text(encoding="utf-8")
        self.assertIn('"target_domain": "unknown"', report)
        self.assertIn('"findings": []', report)
        self.assertIn("Interesting header", report)


class TestEmailReport(unittest.TestCase):

    def setUp(self):
        kb.kb.cleanup()
        self.smtp_server = LocalSMTPServer()
        self.smtp_server.start()
        self.addCleanup(self.smtp_server.stop)

        self.plugin = email_report()
        self.plugin.set_knowledge_base(kb.kb)
        self.plugin.set_configuration(cf)
        self.plugin.set_output(om.out)
        options = self.plugin.get_options()
        options["smtpServer"].set_value("127.0.0.1")
        options["smtpPort"].set_value(self.smtp_server.port)
        options["toAddrs"].set_value("to@w3af.org")
        options["fromAddr"].set_value("from@w3af.org")
        self.plugin.set_options(options)

    def tearDown(self):
        kb.kb.cleanup()

    def test_no_targets_no_email(self):
        self.plugin.end()
        self.assertEqual(self.smtp_server.inbox, [])

    def test_report_is_sent_only_once(self):
        _save_config(self, "targets", [TARGET])
        vuln = Vuln("SQL injection", VULN_DESC, severity.HIGH, 1, "sqli")
        vuln.set_url(TARGET)
        kb.kb.append("sqli", "sqli", vuln)

        self.plugin.log_enabled_plugins({}, {})
        self.plugin.end()
        self.plugin.end()

        self.assertEqual(len(self.smtp_server.inbox), 1)

    def test_smtp_errors_are_reported(self):
        _save_config(self, "targets", [TARGET])
        self.plugin.log_enabled_plugins({}, {})
        self.plugin.smtpPort = _closed_port()

        self.plugin.end()

        self.assertEqual(self.smtp_server.inbox, [])

    def test_long_desc(self):
        self.assertIn("email", self.plugin.get_long_desc())


class TestHTMLFileMessages(unittest.TestCase):

    def setUp(self):
        self.plugin = html_file()

    def test_messages_are_collected(self):
        self.plugin.debug("hidden debug")
        self.plugin._verbose = True
        self.plugin.debug("debug message")
        self.plugin.error("error message")
        self.plugin.console("console message")

        collected = [(kind, msg) for _, kind, msg in self.plugin._additional_info]
        self.assertEqual(
            collected,
            [
                ("debug", "debug message"),
                ("error", "error message"),
                ("console", "console message"),
            ],
        )

    def test_long_desc(self):
        self.assertIn("HTML report", self.plugin.get_long_desc())

    def test_dumps_for_unknown_history_id(self):
        create_temp_dir()
        self.assertIsNone(request_dump(987654321))
        self.assertIsNone(response_dump(987654321))

    def test_unknown_severity_icon(self):
        icon = get_severity_icon(self.plugin.template_root, "unknown-severity")
        self.assertEqual(icon, "data:image/png;base64,")


class TestTextFile(unittest.TestCase):

    def setUp(self):
        create_temp_dir()
        self.directory = _temp_dir(self)
        self.output_file = os.path.join(self.directory, "output.txt")
        self.http_file = os.path.join(self.directory, "output-http.txt")
        self.plugin = text_file()
        self.plugin.set_output(om.out)

    def _configure(self, output_file, http_file):
        options = self.plugin.get_options()
        options["output_file"].set_value(output_file)
        options["http_output_file"].set_value(http_file)
        self.plugin.set_options(options)

    def _request_response(self):
        request = HTTPRequest(TARGET)
        headers = Headers([("content-type", "text/html")])
        response = HTTPResponse(200, "body", headers, TARGET, TARGET, _id=7)
        return request, response

    def test_output_file_in_missing_directory_is_rejected(self):
        missing = os.path.join(self.directory, "missing", "output.txt")
        self.assertRaises(
            BaseFrameworkException, self._configure, missing, self.http_file
        )

    def test_unopenable_output_file(self):
        self.plugin._output_file_name = os.path.join(self.directory, "missing", "x")
        self.plugin._http_file_name = self.http_file

        self.assertRaises(BaseFrameworkException, self.plugin.information, "msg")

    def test_messages_are_written(self):
        self._configure(self.output_file, self.http_file)

        self.plugin.error("error message")
        self.plugin.console("console message")
        self.plugin.information(None)
        self.plugin.flush()
        self.plugin.end()

        lines = Path(self.output_file).read_text().splitlines()
        self.assertTrue(lines[0].endswith("error] error message"))
        self.assertTrue(lines[1].endswith("console] console message"))
        self.assertTrue(lines[2].endswith("information] "))

    def test_http_log_ignored_for_dev_null(self):
        self._configure(self.output_file, DEV_NULL)

        self.plugin.log_http(*self._request_response())
        self.plugin.flush()
        self.plugin.end()

        self.assertIsNone(self.plugin._http)

    def test_write_errors_disable_the_output(self):
        self._configure(self.output_file, self.http_file)
        self.plugin.end()

        self.plugin.information("after close")
        self.plugin.information("ignored")
        self.plugin.log_http(*self._request_response())
        self.plugin.log_http(*self._request_response())

        self.assertIsNone(self.plugin._log)
        self.assertIsNone(self.plugin._http)

    def test_first_write_initializes_files(self):
        self.plugin._output_file_name = self.output_file
        self.plugin._http_file_name = self.http_file

        self.plugin.information("lazy init")
        self.plugin.end()

        self.assertIn("lazy init", Path(self.output_file).read_text())

    def test_long_desc(self):
        self.assertIn("text file", self.plugin.get_long_desc())


cf = Config()
