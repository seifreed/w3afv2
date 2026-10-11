"""
strategy.py

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

import logging

from w3af.core.controllers.core_helpers.fuzzable_request_router import (
    FuzzableRequestRouter,
)
from w3af.core.controllers.core_helpers.scan_runtime_context import (
    ScanRuntimeContext,
)
from w3af.core.controllers.core_helpers.strategy_consumer_runtime import (
    StrategyConsumerRuntime,
)
from w3af.core.controllers.core_helpers.strategy_observers.strategy_observer import (
    StrategyObserver,
)
from w3af.core.controllers.core_helpers.target_validation import (
    alert_if_target_is_301_all,
    replace_targets_with_redir,
    setup_404_detection,
    verify_target_server_up,
)

logger = logging.getLogger(__name__)


class CoreStrategy:
    """
    This is the simplest scan strategy which follows this logic:

        while new_things_found():
            discovery()
            bruteforce()
        audit(things)

    It has been w3af's main algorithm for a while, and what we want to do now
    is to decouple it from the core in order to make experiments and implement
    new / faster algorithms.

    Use this strategy as a base for your experiments!
    """

    def __init__(
        self,
        scan_context: ScanRuntimeContext,
        knowledge_base,
        output,
        configuration,
    ):
        self._scan_context = scan_context
        self._knowledge_base = knowledge_base
        self._output = output
        self._configuration = configuration

        self._consumer_runtime = StrategyConsumerRuntime(
            self._scan_context,
            self._knowledge_base,
            self._output,
            self._configuration,
        )
        self._request_router = FuzzableRequestRouter(
            self._scan_context,
            self._consumer_runtime,
            self._output,
            self._configuration,
        )

        # Also use this method to clear observers
        self._observers: list[StrategyObserver] = []

    def get_grep_consumer(self):
        return self._consumer_runtime.get_grep_consumer()

    def get_audit_consumer(self):
        return self._consumer_runtime.get_audit_consumer()

    def get_discovery_consumer(self):
        return self._consumer_runtime.get_discovery_consumer()

    def get_bruteforce_consumer(self):
        return self._consumer_runtime.get_bruteforce_consumer()

    def set_consumers_to_none(self):
        self._consumer_runtime.reset()
        self._observers = []

    def start(self):
        """
        Starts the work!
        User interface coders: Please remember that you have to call
        core.plugins.init_plugins() method before calling start.

        :return: No value is returned.
        """
        try:
            verify_target_server_up(
                self._scan_context, self._output, self._configuration
            )
            replace_targets_with_redir(
                self._scan_context, self._output, self._configuration
            )
            alert_if_target_is_301_all(
                self._scan_context,
                self._knowledge_base,
                self._output,
                self._configuration,
            )

            self._setup_grep()
            self._setup_auth()
            self._setup_crawl_infrastructure()
            self._setup_audit()
            self._setup_bruteforce()

            self._setup_observers()
            setup_404_detection(self._scan_context, self._output, self._configuration)

            self._seed_discovery()

            self._fuzzable_request_router()

        except Exception as e:
            logger.debug("Unhandled exception in start()", exc_info=True)
            self._output.debug(f'strategy.start() found exception "{e}"')

            try:
                # Terminate the consumers, exceptions at this level stop the scan
                self.terminate()
            finally:
                # While the consumers might have finished, they certainly queue
                # tasks in the core's worker_pool, which need to be processed
                # too
                self._scan_context.worker_pool.finish()

            raise

        else:
            # Wait for all consumers to finish
            self.join_all_consumers()

            # While the consumers might have finished, they certainly queue
            # tasks in the core's worker_pool, which need to be processed too
            self._scan_context.worker_pool.finish()

            # And also teardown all the observers
            self._teardown_observers()

    def stop(self):
        self.terminate()
        self._output.debug("strategy.stop() completed")

    def terminate(self):
        """
        Consume (without processing) all queues with data which are in
        the consumers and then send a poison-pill to that queue.
        """
        self._consumer_runtime.terminate()

        # The observers run their own (non-daemon) threads, which need to be
        # stopped before set_consumers_to_none() forgets about them
        self._teardown_observers()
        self.set_consumers_to_none()

    def join_all_consumers(self):
        """
        Wait for the consumers to process all their work, the order seems to be
        important (not actually verified nor tested) but basically we first
        finish the consumers that generate URLs and then the ones that consume
        them.
        """
        self._output.debug("Joining all consumers (teardown phase)")

        self._teardown_crawl_infrastructure()

        self._teardown_audit()
        self._teardown_bruteforce()

        self._teardown_auth()
        self._teardown_grep()

    def clear_queue_speed_data(self):
        """
        When one of the consumers finishes its work the speed of all queues is
        heavily impacted. A few examples:
            * Crawl finishes: The audit input queue speed goes to zero
            * Crawl and audit finish: The grep input queue speed goes to zero

        In order to quickly clear the previous state of the queue and reflect
        the new speed, it is important to clear the old (now useless data) which
        is used to calculate the input / output speeds and is now useless since
        the number of consumers has changed.
        """
        self._consumer_runtime.clear_queue_speed_data()

    def add_observer(self, observer):
        self._observers.append(observer)

    def _setup_observers(self):
        """
        "Forward" the observer to the consumers
        :return: None
        """
        for consumer in {
            self.get_audit_consumer(),
            self.get_bruteforce_consumer(),
            self.get_discovery_consumer(),
            self.get_grep_consumer(),
        }:
            if consumer is not None:
                for observer in self._observers:
                    consumer.add_observer(observer)

    def _fuzzable_request_router(self):
        """Route scan results through the consumer runtime."""
        self._request_router.route()

    def _setup_crawl_infrastructure(self):
        self._consumer_runtime.setup_crawl_infrastructure()

    def _setup_grep(self):
        self._consumer_runtime.setup_grep()

    def _teardown_grep(self):
        self._consumer_runtime.teardown_grep()

    def _teardown_audit(self):
        self._consumer_runtime.teardown_audit()

    def _teardown_auth(self):
        self._consumer_runtime.teardown_auth()

    def _teardown_bruteforce(self):
        self._consumer_runtime.teardown_bruteforce()

    def _teardown_crawl_infrastructure(self):
        self._consumer_runtime.teardown_crawl_infrastructure()

    def _teardown_observers(self):
        self._output.debug("Called strategy._teardown_observers()")

        for observer in self._observers:
            observer.end()

    def _seed_discovery(self):
        self._consumer_runtime.seed_discovery()

    def _setup_bruteforce(self):
        self._consumer_runtime.setup_bruteforce()

    def _setup_auth(self, timeout=5):
        self._consumer_runtime.setup_auth(timeout)

    def _setup_audit(self):
        self._consumer_runtime.setup_audit()
