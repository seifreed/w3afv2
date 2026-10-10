"""
w3af_core.py

Copyright 2006 Andres Riancho

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
import pprint
import threading
import traceback

from w3af.core.controllers.core_helpers.exception_handler import ExceptionHandler
from w3af.core.controllers.core_helpers.fingerprint_404 import fingerprint_404_singleton
from w3af.core.controllers.core_helpers.plugins import CorePlugins
from w3af.core.controllers.core_helpers.profiles import CoreProfiles
from w3af.core.controllers.core_helpers.runtime_directories import (
    prepare_home_directory,
    prepare_tmp_directory,
)
from w3af.core.controllers.core_helpers.scan_environment_validator import (
    ScanEnvironmentValidator,
)
from w3af.core.controllers.core_helpers.scan_stop_controller import (
    ScanStopController,
)
from w3af.core.controllers.core_helpers.status import (
    PAUSED,
    RUNNING,
    STOPPED,
    CoreStatus,
)
from w3af.core.controllers.core_helpers.status_consumers import ConsumerMetrics
from w3af.core.controllers.core_helpers.strategy import CoreStrategy
from w3af.core.controllers.core_helpers.strategy_observers.disk_space_observer import (
    DiskSpaceObserver,
)
from w3af.core.controllers.core_helpers.strategy_observers.thread_count_observer import (
    ThreadCountObserver,
)
from w3af.core.controllers.core_helpers.strategy_observers.thread_state_observer import (
    ThreadStateObserver,
)
from w3af.core.controllers.core_helpers.target import CoreTarget
from w3af.core.controllers.core_helpers.worker_pool_manager import (
    WorkerPoolManager,
)
from w3af.core.controllers.misc.dns_cache import enable_dns_cache
from w3af.core.controllers.misc.get_w3af_version import get_w3af_version_minimal
from w3af.core.controllers.misc_settings import MiscSettings
from w3af.core.controllers.output_manager import (
    create_output_manager,
)
from w3af.core.controllers.output_manager.logging_bridge import configure_data_logging
from w3af.core.controllers.parser_worker import register_parser_multiprocessing
from w3af.core.controllers.profiling import start_profiling, stop_profiling
from w3af.core.data.kb import knowledge_base as kb_store
from w3af.core.data.kb.config import cf
from w3af.core.data.misc.number_generator import consecutive_number_generator
from w3af.core.data.parsers import parser_cache
from w3af.core.data.url.extended_urllib import ExtendedUrllib
from w3af.core.exceptions import (
    ScanMustStopByUnknownReasonExc,
    ScanMustStopByUserRequest,
    ScanMustStopException,
)
from w3af.core.filesystem import remove_temp_dir
from w3af.core.paths import get_home_dir

NO_MEMORY_MSG = (
    "The operating system was unable to allocate memory for"
    " the Python interpreter (MemoryError). This usually happens"
    " when the OS does not have a mounted swap disk, the"
    " hardware where w3af is running has less than 1GB RAM,"
    " there are many processes running and consuming memory,"
    " or w3af is using more memory than expected."
)


class w3afCore:
    """
    This is the core of the framework, it calls all plugins, handles exceptions,
    coordinates all the work, creates threads, etc.

    :author: Andres Riancho (andres.riancho@gmail.com)
    """

    # Note that the number of worker threads might be modified
    # by the extended url library. When errors appear the worker
    # thread number is reduced, when no errors are found the
    # worker thread count is increased to provide more speed.
    #
    # This only makes sense as long as the worker threads are
    # mostly used for sending HTTP requests (which is the case
    # for the current w3af version).
    WORKER_THREADS = 30
    MIN_WORKER_THREADS = 20
    MAX_WORKER_THREADS = 100

    WORKER_INQUEUE_MAX_SIZE = WORKER_THREADS * 20
    WORKER_MAX_TASKS = 20

    # Seconds to wait for the scan to stop after the user requested it
    STOP_TIMEOUT = 10
    STOP_LOOP_DELAY = 0.5

    def __init__(self, knowledge_base: kb_store.DBKnowledgeBase | None = None):
        """
        Init some variables and files.
        Create the URI opener.
        """
        # Make sure we get a fresh new instance of the output manager
        self._configuration = cf
        self._misc_settings = MiscSettings(self._configuration)
        manager, output = create_output_manager()
        configure_data_logging(output)
        register_parser_multiprocessing(manager)
        self._output = output
        self._output_manager = manager
        self.knowledge_base = knowledge_base or kb_store.kb
        self._worker_pool_manager = WorkerPoolManager(
            output,
            self.WORKER_THREADS,
            self.WORKER_INQUEUE_MAX_SIZE,
            self.WORKER_MAX_TASKS,
        )

        # FIXME: In the future, when the output_manager is not an awful
        # singleton anymore, this line should be removed and the output_manager
        # object should take a w3afCore object as a parameter in its __init__
        manager.set_w3af_core(self, output)

        # This is more than just a debug message, it's a way to force the
        # output manager thread to start it's work. I would start that thread
        # on output manager instantiation but there are issues with starting
        # threads at module import time.
        output.debug(f"Created new w3afCore instance: {id(self)}")

        # Create some directories, do this every time before starting a new
        # scan and before doing any other core init because these are widely
        # used
        prepare_home_directory()
        prepare_tmp_directory()
        # We want to have only one exception handler instance during the whole
        # w3af process. The data captured by it will be cleared before starting
        # each scan, but we want to keep the same instance after a scan because
        # we'll extract info from it.
        self.exception_handler = ExceptionHandler(output, self._configuration)

        # These are some of the most important moving parts in the w3afCore
        # they basically handle every aspect of the w3af framework. I create
        # these here because they are used by the UIs even before starting a
        # scan.
        self.profiles = CoreProfiles(self, self._configuration)
        self.plugins = CorePlugins(self, output, manager)
        self.target = CoreTarget(cf)
        self._environment_validator = ScanEnvironmentValidator(
            self.plugins, self.target
        )
        self.strategy = CoreStrategy(self, self.knowledge_base, output, cf)
        self.status = CoreStatus(
            output,
            ConsumerMetrics(self.strategy, lambda: self.worker_pool),
        )

        # Create the URI opener object
        self.uri_opener = ExtendedUrllib(output.log_http)
        self.uri_opener.set_worker_pool_provider(
            lambda: self.worker_pool,
            self.MIN_WORKER_THREADS,
            self.MAX_WORKER_THREADS,
        )
        self._stop_controller = ScanStopController(
            output,
            self.uri_opener,
            lambda: self.strategy,
            lambda: self.status,
            self._worker_pool_manager.terminate,
            lambda: self.STOP_TIMEOUT,
            lambda: self.STOP_LOOP_DELAY,
        )

        # Keep track of first scan to call cleanup or not
        self._first_scan = True

    def scan_start_hook(self):
        """
        Create directories, threads and consumers required to perform a w3af
        scan. Used both when we init the core and when we want to clear all
        the previous results and state from an old scan and start again.

        :return: None
        """
        # Create this again just to clear the internal states
        scans_completed = self.status.scans_completed

        start_profiling(self, self._output, self._output_manager)

        if not self._first_scan:
            self.cleanup()

        else:
            # Create some directories, do this every time before starting a new
            # scan and before doing any other core init because these are
            # widely used
            prepare_home_directory()
            prepare_tmp_directory()

            enable_dns_cache(self._output)

        # Reset global sequence number generator
        consecutive_number_generator.reset()

        # Now that we know we're going to run a new scan, overwrite the old
        # strategy which might still have data stored in it and create a new
        # one
        self.strategy = CoreStrategy(
            self, self.knowledge_base, self._output, self._configuration
        )
        self.status = CoreStatus(
            self._output,
            ConsumerMetrics(self.strategy, lambda: self.worker_pool),
            scans_completed=scans_completed,
        )
        self.status.start()
        self.strategy.add_observer(DiskSpaceObserver())
        self.strategy.add_observer(ThreadCountObserver(self._output))
        self.strategy.add_observer(ThreadStateObserver(self._output))

        # Init the 404 detection for the whole framework
        fp_404_db = fingerprint_404_singleton(self._output, cleanup=True)
        fp_404_db.set_url_opener(self.uri_opener)

    def start(self):
        """
        The user interfaces call this method to start the whole scanning
        process.

        @raise: This method raises almost every possible exception, so please
                do your error handling!
        """
        self._output.debug("Called w3afCore.start()")

        self.scan_start_hook()

        try:
            # Just in case the GUI / Console forgot to do this...
            self.verify_environment()
        except Exception as e:
            error = (
                'verify_environment() raised an exception: "%s". This'
                " should never happen. Are you (UI developer) sure that"
                " you called verify_environment() *before* start() ?"
            )
            self._output.error(error % e)
            raise

        # Let the output plugins know what kind of plugins we're
        # using during the scan
        self._output_manager.log_enabled_plugins(
            self.plugins.get_all_enabled_plugins(),
            self.plugins.get_all_plugin_options(),
        )

        self._first_scan = False

        self._output.debug(
            f"Starting the scan using w3af version {get_w3af_version_minimal()}"
        )

        try:
            self._run_strategy()

        finally:
            time_spent = self.status.get_scan_time()

            self._output.information(f"Scan finished in {time_spent}")
            self._output.information("Stopping the core...")

            self.strategy.stop()
            self.scan_end_hook()

            # Make sure this line is the last one. This avoids race conditions
            # https://github.com/andresriancho/w3af/issues/1487
            self.status.scan_finished()

    def _run_strategy(self):
        """Run the strategy and translate expected scan-level failures."""
        try:
            self.strategy.start()
        except MemoryError:
            print(NO_MEMORY_MSG)
            self._output.error(NO_MEMORY_MSG)

        except OSError as os_err:
            # https://github.com/andresriancho/w3af/issues/10186
            # OSError: [Errno 12] Cannot allocate memory
            if os_err.errno == errno.ENOMEM:
                print(NO_MEMORY_MSG)
                self._output.error(NO_MEMORY_MSG)

            # https://github.com/andresriancho/w3af/issues/9653
            # IOError: [Errno 28] No space left on device
            elif os_err.errno == errno.ENOSPC:
                msg = (
                    "The w3af scan will stop because the file system"
                    ' is running low on free space. Check the "%s" directory'
                    " size, overall disk usage and start the scan again."
                )
                msg %= get_home_dir()

                print(msg)
                self._output.error(msg)
            else:
                raise

        except threading.ThreadError as te:
            handle_threading_error(self.status.scans_completed, te)

        except ScanMustStopByUserRequest as sbur:
            # I don't have to do anything here, since the user is the one that
            # requested the scanner to stop. From here the code continues at the
            # "finally" clause, which simply shows a message saying that the
            # scan finished.
            self._output.information(f"{sbur}")

        except ScanMustStopByUnknownReasonExc:
            #
            # If the extended_urllib module raises this type of exception we'll
            # just re-raise. This leads to the exception_handler catching the
            # exception, and if we're lucky users reporting it to our issue
            # tracker
            #
            raise

        except ScanMustStopException as wmse:
            error = (
                "The following error was detected and could not be" " resolved:\n%s\n"
            )
            self._output.error(error % wmse)

        except Exception as e:
            msg = 'Unhandled exception "%s", traceback:\n%s'

            # Exceptions raised in the consumers carry the traceback of the
            # thread where they were originally raised
            traceback_string = getattr(
                e, "original_traceback_string", traceback.format_exc()
            )

            self._output.error(msg % (e, traceback_string))
            raise

    @property
    def worker_pool(self):
        return self._worker_pool_manager.get_pool()

    @property
    def output(self):
        return self._output

    @property
    def configuration(self):
        return self._configuration

    def can_cleanup(self):
        return self.status.get_simplified_status() == STOPPED

    def cleanup(self):
        """
        The GTK user interface calls this when a scan has been stopped
        (or ended successfully) and the user wants to start a new scan.
        All data from the kb is deleted.

        :return: None
        """
        # End the ExtendedUrllib (clear the cache and close connections), this
        # is only useful if there was a previous scan and the user is starting
        # a new one.
        #
        # Please note that I'm not putting this end() thing in scan_end_hook
        # because I want to be able to access the History() item even after the
        # scan has finished to give the user access to the HTTP request and
        # response associated with a vulnerability
        self.uri_opener.restart()
        self.uri_opener.set_exploit_mode(False)

        # If this is not the first scan, I want to clear the old bug data
        # that might be stored in the exception_handler.
        self.exception_handler.clear()

        # Clean all data that is stored in the kb
        self.knowledge_base.cleanup()

        # Stop the parser subprocess
        parser_cache.dpc.clear()
        self._output_manager.stop()

        # Remove the xurllib cache, bloom filters, DiskLists, etc.
        #
        # This needs to be done here and not in stop() because we want to keep
        # these files (mostly the HTTP request/response data) for the user to
        # analyze in the GUI after the scan has finished
        remove_temp_dir(ignore_errors=True)

        # Not cleaning the config is a FEATURE, because the user is most likely
        # going to start a new scan to the same target, and he wants the proxy,
        # timeout and other configs to remain configured as he did it the first
        # time.
        # reload(cf)

        # It is also a feature to keep the misc settings from the last run, this
        # means that we don't cleanup the misc settings.

        # Not calling:
        # self.plugins.zero_enabled_plugins()
        # because I want to keep the selected plugins and configurations

    def can_stop(self):
        return self.status.get_simplified_status() in (RUNNING, PAUSED)

    def stop(self):
        """
        This method is called by the user interface layer, when the user
        "clicks" on the stop button.

        :return: None. The stop method can take some seconds to return.
        """
        self._stop_controller.stop()

    def quit(self):
        """
        The user wants to exit w3af ASAP, so we stop the scan and exit.
        """
        self.stop()
        self.uri_opener.end()

        # Remove the xurllib cache, bloom filters, DiskLists, etc.
        #
        # This needs to be done here and not in stop() because we want to keep
        # these files (mostly the HTTP request/response data) for the user to
        # analyze in the GUI after the scan has finished
        remove_temp_dir(ignore_errors=True)

        # Stop the parser subprocess
        parser_cache.dpc.clear()

    def pause(self, pause_yes_no):
        """
        Pauses/Un-Pauses scan.
        :param pause_yes_no: True if the UI wants to pause the scan.
        """
        self.status.pause(pause_yes_no)
        self.strategy.pause(pause_yes_no)
        self.uri_opener.pause(pause_yes_no)

    def verify_environment(self):
        self._environment_validator.validate()

    def _terminate_worker_pool(self):
        self._worker_pool_manager.terminate()

    def scan_end_hook(self):
        """
        This method is called when the process ends normally or by an error.
        """
        stop_profiling(self, self._output, self._output_manager)
        parser_cache.dpc.clear()

        try:
            #
            # Close the output manager, this needs to be done BEFORE the end()
            # in uri_opener because some plugins (namely xml_output) use the
            # data from the history in their end() method.
            #
            # Also needs to be done before target.clear() because some plugins
            # need to access the target data stored in cf
            #
            self._output.debug("Calling end_output_plugins()")
            self._output_manager.end_output_plugins()
        finally:
            self._terminate_worker_pool()

            self.exploit_phase_prerequisites()

            # Remove all references to plugins from memory
            self.plugins.zero_enabled_plugins()

            # No targets to be scanned
            self.target.clear()

            # Status
            self.status.stop()

        self._output.debug("scan_end_hook() completed")

    def exploit_phase_prerequisites(self):
        """
        This method is just a way to group all the things that we'll need
        from the core during the exploitation phase. In other words, which
        internal objects do I need alive after a scan?
        """
        self._output.debug("Setting exploit phase prerequisites")

        # We disable raising the exception, so we do this only once and don't
        # affect other parts of the tool such as the exploitation or manual HTTP
        # request sending from the GUI
        #
        # https://github.com/andresriancho/w3af/issues/2704
        # https://github.com/andresriancho/w3af/issues/2711
        self.uri_opener.clear()

        # Disable some internal checks so the exploits can "bend" the matrix
        self.uri_opener.set_exploit_mode(True)


class ThreadingResourceError(Exception):
    """
    Raised when the process is unable to create or manage more threads.
    """


def handle_threading_error(scans_completed, threading_error):
    """
    Catch threading errors such as "error: can't start new thread"
    and handle them in a specific way
    """
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
