"""
exception_handler.py

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
import secrets
import tempfile
import threading
import traceback
from copy import copy
from typing import TypedDict

from w3af.core.controllers.core_helpers.status import CoreStatus
from w3af.core.controllers.exception_handling.cleanup_bug_report import (
    cleanup_bug_report,
)
from w3af.core.data.fuzzer.utils import rand_alnum
from w3af.core.data.url.exceptions import HTTPRequestException
from w3af.core.exceptions import (
    ScanMustStopByUnknownReasonExc,
    ScanMustStopByUserRequest,
    ScanMustStopException,
)
from w3af.core.traceback_utils import get_exception_location

ExceptionSummaryEntry = tuple[object, object, Exception, str | None]


class ExceptionSummary(TypedDict):
    total_exceptions: int
    exceptions: dict[object, list[ExceptionSummaryEntry]]


def debug_enabled():
    """
    :return: True when the DEBUG environment variable asks for every plugin
             exception to propagate instead of being stored
    """
    return os.environ.get("DEBUG", "0") == "1"


class ExceptionHandler:
    """
    This class handles exceptions generated while running plugins, usually
    the handling is just to store the traceback for later processing.

    :author: Andres Riancho (andres.riancho@gmail.com)
    """

    MAX_EXCEPTIONS_PER_PLUGIN = 3
    NO_HANDLING: tuple[type[BaseException], ...] = (
        MemoryError,
        OSError,
        ScanMustStopByUnknownReasonExc,
        ScanMustStopException,
        ScanMustStopByUserRequest,
        HTTPRequestException,
    )

    def __init__(self, output, configuration):
        self._exception_data = []
        self._lock = threading.RLock()
        self._output = output
        self._configuration = configuration

        self._scan_id = None

    def handle_exception_data(self, exception_data):
        self._raise_if_exception_must_propagate(
            exception_data.exception, exception_data.exception.__traceback__
        )
        self._store_exception_data(exception_data)

    def handle(self, current_status, exception, exec_info, enabled_plugins):
        """
        This method stores the current status and the exception for later
        processing. If there are already too many stored exceptions for this
        plugin then no action is taken.

        :param current_status: Pointer to the core_helpers.status module
        :param exception: The exception that was raised
        :param exec_info: The exec info as returned by sys module. In some
                          scenarios the data can be (partially) incomplete.
                          except_type and except_class might be None; or all the
                          three fields might be None.
        :param enabled_plugins: A string as returned by helpers.pprint_plugins.
                                First I thought about getting the enabled_plugins
                                after the scan finished, but that proved to be
                                an incorrect approach since the UI and/or
                                strategy could simply remove that information as
                                soon as the scan finished.

        :return: None
        """
        _, _, tb = exec_info

        #
        # There are some exceptions, that because of their nature, can't be
        # handled here. Raise them so that w3afCore.py, most likely to the
        # except lines around self.strategy.start(), can decide what to do
        #
        self._raise_if_exception_must_propagate(exception, tb)

        #
        # Now we really handle the exception that was produced by the plugin in
        # the way we want to.
        #
        edata = ExceptionData(
            current_status,
            exception,
            tb,
            enabled_plugins,
            self._configuration,
        )
        self._store_exception_data(edata)

    def _raise_if_exception_must_propagate(self, exception, tb):
        if isinstance(exception, self._unhandled_exception_types()):
            raise exception.with_traceback(tb)

        if self._configuration.get("stop_on_first_exception"):
            raise exception.with_traceback(tb)

    def _store_exception_data(self, edata):
        edata.release_traceback()

        with self._lock:
            count = 0
            for stored_edata in self._exception_data:
                if (
                    edata.plugin == stored_edata.plugin
                    and edata.phase == stored_edata.phase
                ):
                    count += 1

            if count < self.MAX_EXCEPTIONS_PER_PLUGIN:
                self._exception_data.append(edata)
                msg = edata.get_summary()
                msg += (
                    " The scan will continue but some vulnerabilities might"
                    " not be identified."
                )
                self._output.error(msg)

        filename = self.write_crash_file(edata)

        self._output.debug(f'Logged "{edata.get_exception_class()}" to "{filename}"')

        # Also send to the output plugins so they can store it the right way
        self._output.log_crash(edata.get_details())

    def _unhandled_exception_types(self):
        if debug_enabled():
            return (*self.NO_HANDLING, Exception)

        return self.NO_HANDLING

    def write_crash_file(self, edata):
        """
        Writes the exception data to a random file in /tmp/ right after the
        exception is found, for internal/debugging usage.

        :return: None
        """
        filename = f"w3af-crash-{rand_alnum(5)}.txt"
        filename = os.path.join(tempfile.gettempdir(), filename)
        with open(filename, "w", encoding="utf-8") as crash_dump:
            crash_dump.write(edata.get_details())
        return filename

    def clear(self):
        self._exception_data = []

    def get_all_exceptions(self):
        return self._exception_data

    def get_unique_exceptions(self):
        """
        Filters the found exceptions to only show unique "bugs". We filter based
        on the lineno and filename of each ExceptionData stored in
        self._exception_data

        :return: A filtered exception list
        """
        filtered_exceptions: list[ExceptionData] = []

        for edata in self.get_all_exceptions():
            for unique in filtered_exceptions:
                if edata.lineno == unique.lineno and edata.filename == unique.filename:
                    break
            else:
                filtered_exceptions.append(edata)

        return filtered_exceptions

    def generate_summary_str(self):
        """
        :return: A string with a summary of the exceptions found during the
                 current scan. This is mostly used for printing in the console
                 but can be used anywhere.

        @see: generate_summary method for a way of getting a summary in a
              different format.
        """
        summary = self.generate_summary()

        if not summary["total_exceptions"]:
            fmt_without_exceptions = (
                "No exceptions were raised during scan with id: %s."
            )
            without_exceptions = fmt_without_exceptions % self.get_scan_id()
            return without_exceptions

        fmt_with_exceptions = (
            "During the current scan (with id: %s) w3af"
            " caught %s exceptions in it's plugins. The"
            " scan was able to continue by ignoring those"
            " failures but the result is most likely"
            " incomplete.\n"
            "\n"
            "These are the phases and plugins that raised"
            " exceptions:\n"
            "%s\n"
            "We recommend you report these vulnerabilities"
            " to the developers in order to help increase"
            " the project's stability.\n"
            "\n"
            'To report these bugs just run the "report"'
            " command."
        )

        phase_plugin_str = ""

        for phase in summary["exceptions"]:
            for plugin, fr, exception, _ in summary["exceptions"][phase]:
                phase_plugin_str += f"- {phase}.{plugin}\n"

        with_exceptions = fmt_with_exceptions % (
            self.get_scan_id(),
            summary["total_exceptions"],
            phase_plugin_str,
        )
        return with_exceptions

    def generate_summary(self):
        """
        :return: A dict with information about exceptions.
        """
        res: ExceptionSummary = {
            "total_exceptions": len(self._exception_data),
            "exceptions": {},
        }
        exception_dict = res["exceptions"]

        for exception in self._exception_data:
            phase = exception.phase

            data = (
                exception.plugin,
                exception.fuzzable_request,
                exception.exception,
                exception.traceback_str,
            )

            if phase not in exception_dict:
                exception_dict[phase] = [data]
            else:
                exception_dict[phase].append(data)

        return res

    def get_scan_id(self):
        """
        :return: A scan identifier to bind all bug reports together so that we
                 can understand them much better when looking at the individual
                 Github bug reports.

                 Note that this will NOT leak any personal information to our
                 systems.
        """
        if self._scan_id is None:
            self._scan_id = secrets.token_hex(5)

        return self._scan_id


class ExceptionData:
    def __init__(
        self, current_status, e, tb, enabled_plugins, configuration, store_tb=True
    ):
        """
        :param current_status: The CoreStatus instance
        :param e: Exception instance
        :param tb: Traceback or None
        :param enabled_plugins: w3af enabled plugins
        :param store_tb: Keep the exception traceback while a worker transports it
        """
        if not isinstance(e, Exception):
            raise TypeError("e must be an Exception")
        if not isinstance(current_status, CoreStatus):
            raise TypeError("current_status must be a CoreStatus")

        self.traceback_str = None
        self.function_name = None
        self.lineno = None
        self.filename = None
        self.exception: Exception = e
        self.exception_msg = None
        self.exception_class = None
        self.phase = None
        self.plugin = None
        self.status = None
        self.fuzzable_request = None

        self._initialize(
            current_status, e, tb, enabled_plugins, configuration, store_tb
        )

    def _initialize(
        self, current_status, e, tb, enabled_plugins, configuration, store_tb
    ):
        self._initialize_from_exception(e)
        self._initialize_from_traceback(tb, configuration, store_tb)
        self._initialize_from_status(current_status, configuration)
        self._initialize_from_plugins(enabled_plugins)

    def _initialize_from_exception(self, e):
        self.exception = e
        self.exception_msg = str(e)
        self.exception_class = e.__class__.__name__

    def _initialize_from_status(self, current_status, configuration):
        self.phase, self.plugin = current_status.latest_running_plugin()

        #
        # Do not save the CoreStatus instance here without cleaning it first,
        # it will break serialization since the CoreStatus instances have
        # references to a w3afCore instance, which points to a Pool instance
        # that is NOT serializable.
        #
        self.status = copy(current_status)
        self.status.detach_runtime_dependencies()
        self.status.set_output(None)

        self.fuzzable_request = current_status.get_current_fuzzable_request(self.phase)
        self.fuzzable_request = cleanup_bug_report(
            str(self.fuzzable_request), configuration
        )

    def _initialize_from_plugins(self, enabled_plugins):
        self.enabled_plugins = enabled_plugins

    def _initialize_from_traceback(self, tb, configuration, store_tb):
        # Extract the filename and line number where the exception was raised
        _, self.filename, self.function_name, self.lineno = get_exception_location(tb)

        # See add_traceback_string()
        traceback_string = getattr(self.exception, "original_traceback_string", None)
        if traceback_string is None:
            traceback_string = "".join(traceback.format_tb(tb))
            self.exception.original_traceback_string = traceback_string

        self.traceback_str = cleanup_bug_report(traceback_string, configuration)

        if store_tb:
            # The textual report is sufficient after construction. Keeping the
            # traceback would retain every local from the failing frame.
            self.exception.__traceback__ = None

    def release_traceback(self):
        self.exception.__traceback__ = None

    def get_summary(self):
        res = (
            'A "%s" exception was found while running %s.%s on "%s".'
            ' The exception was: "%s" at %s:%s():%s.'
        )
        res = res % (
            self.get_exception_class(),
            self.phase,
            self.plugin,
            self.fuzzable_request,
            self.exception_msg,
            self.filename,
            self.function_name,
            self.lineno,
        )
        return res

    def get_exception_class(self):
        return self.exception_class

    def get_details(self):
        res = self.get_summary()
        res += f" The full traceback is:\n\n{self.traceback_str}"
        return res

    def get_where(self):
        return f"{self.phase}.{self.plugin}:{self.lineno}"

    def to_json(self):
        return {
            "function_name": self.function_name,
            "lineno": self.lineno,
            "exception": self.exception_msg,
            "traceback": self.traceback_str,
            "plugin": str(self.plugin),
            "phase": str(self.phase),
        }

    def __str__(self):
        return self.get_details()

    def __repr__(self):
        return (
            f"<ExceptionData - {self.filename}:{self.lineno} - "
            f'"{self.exception_msg}">'
        )
