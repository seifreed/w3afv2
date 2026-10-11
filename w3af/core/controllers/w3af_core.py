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

import weakref

from w3af.core.controllers.core_helpers import scan_strategy_runner
from w3af.core.controllers.core_helpers.core_resource_lifecycle import (
    CoreResourceLifecycle,
)
from w3af.core.controllers.core_helpers.exception_handler import ExceptionHandler
from w3af.core.controllers.core_helpers.fingerprint_404_lifecycle import (
    Fingerprint404Lifecycle,
)
from w3af.core.controllers.core_helpers.plugins import CorePlugins
from w3af.core.controllers.core_helpers.profiles import CoreProfiles
from w3af.core.controllers.core_helpers.runtime_directories import (
    prepare_home_directory,
    prepare_tmp_directory,
)
from w3af.core.controllers.core_helpers.scan_end_lifecycle import ScanEndLifecycle
from w3af.core.controllers.core_helpers.scan_environment_validator import (
    ScanEnvironmentValidator,
)
from w3af.core.controllers.core_helpers.scan_reset_lifecycle import (
    ScanResetLifecycle,
)
from w3af.core.controllers.core_helpers.scan_start_lifecycle import (
    ScanStartLifecycle,
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
from w3af.core.controllers.misc.dns_cache import DNSCache
from w3af.core.controllers.misc.get_w3af_version import get_w3af_version_minimal
from w3af.core.controllers.misc_settings import MiscSettings
from w3af.core.controllers.output_manager import (
    create_output_manager,
)
from w3af.core.controllers.output_manager.logging_bridge import (
    configure_data_logging,
    remove_data_logging,
)
from w3af.core.controllers.parser_worker import get_parser_worker_bootstrap
from w3af.core.controllers.profiling import start_profiling, stop_profiling
from w3af.core.data.db.dbms import create_temp_db_instance
from w3af.core.data.kb.config import Config
from w3af.core.data.kb.knowledge_base import DBKnowledgeBase
from w3af.core.data.misc.number_generator import NumberGenerator
from w3af.core.data.parsers.mp_document_parser import MultiProcessingDocumentParser
from w3af.core.data.parsers.parser_cache import ParserCache
from w3af.core.data.url.extended_urllib import ExtendedUrllib
from w3af.core.filesystem import remove_temp_dir
from w3af.core.paths import get_home_dir

NO_MEMORY_MSG = scan_strategy_runner.NO_MEMORY_MSG
ThreadingResourceError = scan_strategy_runner.ThreadingResourceError
handle_threading_error = scan_strategy_runner.handle_threading_error
ScanStrategyRunner = scan_strategy_runner.ScanStrategyRunner


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

    def __init__(
        self,
        knowledge_base: DBKnowledgeBase | None = None,
        configuration: Config | None = None,
    ):
        """
        Init some variables and files.
        Create the URI opener.
        """
        # Make sure we get a fresh new instance of the output manager
        self._configuration = Config() if configuration is None else configuration
        self._misc_settings = MiscSettings(self._configuration)
        manager, output = create_output_manager()
        configure_data_logging(output)
        log_queue_provider, worker_initializer = get_parser_worker_bootstrap(manager)
        if knowledge_base is None:
            self._owns_database = True
            self._database = create_temp_db_instance()
            self.knowledge_base = DBKnowledgeBase(db=self._database)
        else:
            self._owns_database = False
            knowledge_base.setup()
            self._database = knowledge_base.db
            self.knowledge_base = knowledge_base
        self._dns_cache = DNSCache(output)
        self._parser_cache = ParserCache(
            mp_parser=MultiProcessingDocumentParser(
                log_queue_provider=log_queue_provider,
                worker_initializer=worker_initializer,
            ),
            db=self._database,
        )
        self._id_generator = NumberGenerator()
        self._worker_pool_manager = WorkerPoolManager(
            output,
            self.WORKER_THREADS,
            self.WORKER_INQUEUE_MAX_SIZE,
            self.WORKER_MAX_TASKS,
        )
        self._resource_lifecycle = CoreResourceLifecycle(
            manager,
            self._dns_cache,
            self._parser_cache,
            self._database if self._owns_database else None,
            self._worker_pool_manager,
        )
        self._resource_finalizer = weakref.finalize(
            self,
            self._resource_lifecycle.stop,
        )
        self._output = output
        self._output_manager = manager
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
        self.target = CoreTarget(self._configuration)
        self._environment_validator = ScanEnvironmentValidator(
            self.plugins, self.target
        )
        self._create_scan_runtime()

        # Create the URI opener object
        self.uri_opener = ExtendedUrllib(
            output.log_http,
            configuration=self._configuration,
            resolver=self._dns_cache.getaddrinfo,
            parser_cache=self._parser_cache,
            id_generator=self._id_generator,
            db=self._database,
        )
        self.uri_opener.set_worker_pool_provider(
            lambda: self.worker_pool,
            self.MIN_WORKER_THREADS,
            self.MAX_WORKER_THREADS,
        )
        self._fingerprint_404_lifecycle = Fingerprint404Lifecycle(
            output,
            self._configuration,
            self._database,
            self.uri_opener,
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
        self._strategy_runner = ScanStrategyRunner(output, get_home_dir)
        self._scan_start_lifecycle = ScanStartLifecycle(
            lambda: self.status,
            lambda: self.strategy,
            lambda: start_profiling(self, self._output, self._output_manager),
            lambda timers: stop_profiling(
                self,
                self._output,
                self._output_manager,
                timers,
            ),
            self.cleanup,
            self._prepare_scan_directories,
            self._create_scan_runtime,
            self._add_scan_observers,
            self._fingerprint_404_lifecycle.start,
        )
        self._scan_end_lifecycle = ScanEndLifecycle(
            output,
            manager,
            self._parser_cache,
            self._scan_start_lifecycle.stop_profiling,
            self._worker_pool_manager.terminate,
            self.exploit_phase_prerequisites,
            self.plugins.zero_enabled_plugins,
            self.target.clear,
            lambda: self.status.stop(),
        )
        self._scan_reset_lifecycle = ScanResetLifecycle(
            self.uri_opener,
            lambda: self.uri_opener.set_exploit_mode(False),
            self.exception_handler,
            self.knowledge_base,
            self._parser_cache,
            self._fingerprint_404_lifecycle,
            self._dns_cache,
            lambda: remove_temp_dir(ignore_errors=True),
        )

    def _prepare_scan_directories(self):
        prepare_home_directory()
        prepare_tmp_directory()

    def _add_scan_observers(self, strategy):
        strategy.add_observer(DiskSpaceObserver())
        strategy.add_observer(ThreadCountObserver(self._output))
        strategy.add_observer(ThreadStateObserver(self._output))

    def scan_start_hook(self):
        """Prepare directories, profiling and runtime for a new scan."""
        self._scan_start_lifecycle.start()

    def _create_scan_runtime(self, scans_completed=0):
        self.strategy = CoreStrategy(
            self, self.knowledge_base, self._output, self._configuration
        )
        self.status = CoreStatus(
            self._output,
            ConsumerMetrics(self.strategy, lambda: self.worker_pool),
            scans_completed=scans_completed,
            id_generator=self._id_generator,
        )

    def is_404(self, http_response):
        """Return whether a response matches this core's 404 fingerprint."""
        return self._fingerprint_404_lifecycle.is_404(http_response)

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

        self._scan_start_lifecycle.mark_scan_started()

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
        self._strategy_runner.run(self.strategy, self.status.scans_completed)

    @property
    def worker_pool(self):
        return self._worker_pool_manager.get_pool()

    @property
    def output(self):
        return self._output

    @property
    def configuration(self):
        return self._configuration

    @property
    def parser_cache(self):
        return self._parser_cache

    @property
    def id_generator(self):
        return self._id_generator

    @property
    def database(self):
        return self._database

    def can_cleanup(self):
        return self.status.get_simplified_status() == STOPPED

    def cleanup(self):
        """
        The GTK user interface calls this when a scan has been stopped
        (or ended successfully) and the user wants to start a new scan.
        All data from the kb is deleted.

        :return: None
        """
        # History remains available after scan_end_hook(); reset only when a
        # new scan is requested.
        self._scan_reset_lifecycle.reset()

        # Not cleaning the config is a FEATURE, because the user is most likely
        # going to start a new scan to the same target, and he wants the proxy,
        # timeout and other configs to remain configured as he did it the first
        # time.
        # Configuration is intentionally preserved for the next scan.

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
        self._scan_start_lifecycle.stop_profiling()
        self.uri_opener.end()
        self._dns_cache.clear()

        self._fingerprint_404_lifecycle.cleanup()

        remove_data_logging(self._output)
        self._resource_finalizer()

        # Remove the xurllib cache, bloom filters, DiskLists, etc.
        #
        # This needs to be done here and not in stop() because we want to keep
        # these files (mostly the HTTP request/response data) for the user to
        # analyze in the GUI after the scan has finished
        remove_temp_dir(ignore_errors=True)

    def pause(self, pause_yes_no):
        """
        Pauses/Un-Pauses scan.
        :param pause_yes_no: True if the UI wants to pause the scan.
        """
        self.status.pause(pause_yes_no)
        self.uri_opener.pause(pause_yes_no)

    def verify_environment(self):
        self._environment_validator.validate()

    def scan_end_hook(self):
        """
        This method is called when the process ends normally or by an error.
        """
        self._scan_end_lifecycle.finish()

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
