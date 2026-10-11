"""Run a scan strategy and translate expected process-level failures."""

import errno
import pprint
import threading
import traceback
from collections.abc import Callable
from typing import Protocol

from w3af.core.exceptions import (
    ScanMustStopByUnknownReasonExc,
    ScanMustStopByUserRequest,
    ScanMustStopException,
)

NO_MEMORY_MSG = (
    "The operating system was unable to allocate memory for"
    " the Python interpreter (MemoryError). This usually happens"
    " when the OS does not have a mounted swap disk, the"
    " hardware where w3af is running has less than 1GB RAM,"
    " there are many processes running and consuming memory,"
    " or w3af is using more memory than expected."
)


class ScanOutput(Protocol):
    """Output operations required by the strategy runner."""

    def error(self, message: str) -> None: ...

    def information(self, message: str) -> None: ...


class ScanStrategy(Protocol):
    """Strategy operation required by the runner."""

    def start(self) -> None: ...


class ThreadingResourceError(Exception):
    """Raised when the process cannot create or manage more threads."""


def handle_threading_error(scans_completed, threading_error):
    """Raise a diagnostic error with the active thread inventory."""
    active_threads = threading.active_count()

    def nice_thread_repr(alive_threads):
        repr_alive = [repr(x) for x in alive_threads]
        repr_alive.sort()
        return pprint.pformat(repr_alive)

    pprint_threads = nice_thread_repr(threading.enumerate())

    msg = (
        'A "%s" threading error was found.\n'
        " The current process has a total of %s active threads and has"
        " completed %s scans. The complete list of threads follows:\n\n%s"
    )
    raise ThreadingResourceError(
        msg % (threading_error, active_threads, scans_completed, pprint_threads)
    )


class ScanStrategyRunner:
    """Execute a strategy while translating expected scan-level failures."""

    def __init__(
        self,
        output: ScanOutput,
        home_directory_provider: Callable[[], str],
    ) -> None:
        self._output = output
        self._home_directory_provider = home_directory_provider

    def run(self, strategy: ScanStrategy, scans_completed: int) -> None:
        """Start the strategy and apply the framework's error policy."""
        try:
            strategy.start()
        except MemoryError:
            self._report_no_memory()
        except OSError as os_error:
            self._handle_os_error(os_error)
        except threading.ThreadError as threading_error:
            handle_threading_error(scans_completed, threading_error)
        except ScanMustStopByUserRequest as stop_request:
            self._output.information(f"{stop_request}")
        except ScanMustStopByUnknownReasonExc:
            raise
        except ScanMustStopException as stop_exception:
            error = "The following error was detected and could not be resolved:\n%s\n"
            self._output.error(error % stop_exception)
        except Exception as exception:
            msg = 'Unhandled exception "%s", traceback:\n%s'
            traceback_string = getattr(
                exception, "original_traceback_string", traceback.format_exc()
            )
            self._output.error(msg % (exception, traceback_string))
            raise

    def _handle_os_error(self, os_error: OSError) -> None:
        if os_error.errno == errno.ENOMEM:
            self._report_no_memory()
            return

        if os_error.errno == errno.ENOSPC:
            msg = (
                "The w3af scan will stop because the file system"
                ' is running low on free space. Check the "%s" directory'
                " size, overall disk usage and start the scan again."
            )
            msg %= self._home_directory_provider()
            print(msg)
            self._output.error(msg)
            return

        raise os_error

    def _report_no_memory(self) -> None:
        print(NO_MEMORY_MSG)
        self._output.error(NO_MEMORY_MSG)
