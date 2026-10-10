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
import queue
import time
from multiprocessing import TimeoutError

import w3af.core.data.kb.config as cf
from w3af.core.constants import POISON_PILL
from w3af.core.controllers.core_helpers.consumers.audit import audit
from w3af.core.controllers.core_helpers.consumers.auth import auth
from w3af.core.controllers.core_helpers.consumers.bruteforce import bruteforce
from w3af.core.controllers.core_helpers.consumers.crawl_infrastructure import (
    CrawlInfrastructure,
)
from w3af.core.controllers.core_helpers.consumers.grep import grep
from w3af.core.controllers.core_helpers.consumers.seed import seed
from w3af.core.controllers.core_helpers.exception_handler import ExceptionData
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

    def __init__(self, w3af_core, knowledge_base, output):
        self._w3af_core = w3af_core
        self._knowledge_base = knowledge_base
        self._output = output

        # Consumer threads
        self._grep_consumer = None
        self._audit_consumer = None
        self._auth_consumer = None

        # Producer/consumer threads
        self._discovery_consumer = None
        self._bruteforce_consumer = None

        # Producer threads
        self._seed_producer = seed(self._w3af_core, self._knowledge_base, self._output)

        # Also use this method to clear observers
        self._observers = []

    def get_grep_consumer(self):
        return self._grep_consumer

    def get_audit_consumer(self):
        return self._audit_consumer

    def get_discovery_consumer(self):
        return self._discovery_consumer

    def get_bruteforce_consumer(self):
        return self._bruteforce_consumer

    def set_consumers_to_none(self):
        # Consumer threads
        self._grep_consumer = None
        self._audit_consumer = None
        self._auth_consumer = None

        # Producer/consumer threads
        self._discovery_consumer = None
        self._bruteforce_consumer = None

        # Producer threads
        self._seed_producer = seed(self._w3af_core, self._knowledge_base, self._output)

        # Also use this method to clear observers
        self._observers = []

    def start(self):
        """
        Starts the work!
        User interface coders: Please remember that you have to call
        core.plugins.init_plugins() method before calling start.

        :return: No value is returned.
        """
        try:
            verify_target_server_up(self._w3af_core, self._output)
            replace_targets_with_redir(self._w3af_core, self._output)
            alert_if_target_is_301_all(
                self._w3af_core, self._knowledge_base, self._output
            )

            self._setup_grep()
            self._setup_auth()
            self._setup_crawl_infrastructure()
            self._setup_audit()
            self._setup_bruteforce()

            self._setup_observers()
            setup_404_detection(self._w3af_core, self._output)

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
                self._w3af_core.worker_pool.finish()

            raise

        else:
            # Wait for all consumers to finish
            self.join_all_consumers()

            # While the consumers might have finished, they certainly queue
            # tasks in the core's worker_pool, which need to be processed too
            self._w3af_core.worker_pool.finish()

            # And also teardown all the observers
            self._teardown_observers()

    def stop(self):
        self.terminate()
        self._output.debug("strategy.stop() completed")

    def pause(self, pause_yes_no):
        # FIXME: Consumers should have something to do with this, most likely
        # another constant similar to the poison pill
        pass

    def terminate(self):
        """
        Consume (without processing) all queues with data which are in
        the consumers and then send a poison-pill to that queue.
        """
        consumers = ["discovery", "audit", "auth", "bruteforce", "grep"]

        for consumer in consumers:

            consumer_inst = getattr(self, f"_{consumer}_consumer")

            if consumer_inst is None:
                msg = "%s consumer is None. Skipping call to terminate()"
                self._output.debug(msg % consumer)
                continue

            self._output.debug(f"Calling terminate() on {consumer} consumer")
            start = time.time()

            # Set it immediately to None to avoid any race conditions where
            # the terminate() method is called twice (from different
            # threads) and before the first call finishes
            #
            # The getattr/setattr tricks are required to make sure that "the
            # real consumer instance" is set to None. Do not modify unless
            # you know what you're doing!
            setattr(self, f"_{consumer}_consumer", None)

            consumer_inst.terminate()

            spent = time.time() - start
            self._output.debug(
                f"terminate() on {consumer} consumer took {spent:.2f} seconds"
            )

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
        consumers = [
            self.get_grep_consumer(),
            self.get_audit_consumer(),
            self.get_discovery_consumer(),
            self.get_bruteforce_consumer(),
        ]

        consumers = [consumer for consumer in consumers if consumer is not None]
        for consumer in consumers:
            consumer.in_queue.clear()

    def add_observer(self, observer):
        self._observers.append(observer)

    def _setup_observers(self):
        """
        "Forward" the observer to the consumers
        :return: None
        """
        for consumer in {
            self._audit_consumer,
            self._bruteforce_consumer,
            self._discovery_consumer,
            self._grep_consumer,
        }:
            if consumer is not None:
                for observer in self._observers:
                    consumer.add_observer(observer)

    def _fuzzable_request_router(self):
        """
        This is one of the most important methods, it will take things from the
        discovery Queue and store them in one or more Queues (audit, bruteforce,
        etc).

        Also keep in mind that is one of the only methods that will be run in
        the "main thread" and lives during the whole scan process.
        """
        _input = [
            self._seed_producer,
            self._discovery_consumer,
            self._bruteforce_consumer,
        ]
        _input = [_f for _f in _input if _f]

        output = [
            self._audit_consumer,
            self._discovery_consumer,
            self._bruteforce_consumer,
        ]
        output = [_f for _f in output if _f]

        # Only check if these have exceptions and bring them to the main
        # thread in order to be handled by the ExceptionHandler and the
        # w3afCore
        _other = [self._audit_consumer, self._auth_consumer, self._grep_consumer]
        _other = [_f for _f in _other if _f]

        finished = set()
        consumer_forced_end = set()

        while True:
            # Get results and handle exceptions
            self._handle_all_consumer_exceptions(_other)

            # Route fuzzable requests
            route_result = self._route_one_fuzzable_request_batch(
                _input, output, finished, consumer_forced_end
            )

            if route_result is None:
                self._output.debug(
                    "The fuzzable request router loop will break."
                    " The scan will stop after all consumers complete"
                    " their teardown() process."
                )
                break

            finished, consumer_forced_end = route_result

            #
            # Handle the case where the scan reached the max time
            #
            if self._scan_reached_max_time():
                msg = (
                    "The scan has reached the maximum scan time of %s minutes."
                    " The scan will end and some vulnerabilities might not be"
                    " identified."
                )
                args = (cf.cf.get("max_scan_time"),)
                self._output.information(msg % args)

                self._w3af_core.stop()
                break

    def _scan_reached_max_time(self):
        """
        Check the user-configured setting and return True if we're 5 minutes
        before the deadline.

        Return True 5 minutes before the `max_scan_time` to give the scan threads
        time to finish and "guarantee" that the scan will be stopped before
        `max_scan_time`.

        :return: True if the scan has reached the `max_scan_time` - 5m.
        """
        # in minutes
        max_scan_time = cf.cf.get("max_scan_time")

        # The default is 0: no limit.
        if max_scan_time == 0:
            return False

        # Get the scan time and compare with the max
        scan_time = self._w3af_core.status.get_run_time()
        return scan_time > max_scan_time

    def _route_one_fuzzable_request_batch(
        self, _input, output, finished, consumer_forced_end
    ):
        """
        Loop once through all input consumers and route their results.

        :return: (finished, consumer_forced_end) or None if we shouldn't call
                 this method anymore.
        """
        for url_producer in _input:

            if len(_input) == len(finished | consumer_forced_end):
                return

            # No more results in the output queue, and had no pending work on
            # the previous loop.
            if url_producer in finished:
                continue

            # Did the producer send a POISON_PILL?
            if url_producer in consumer_forced_end:
                continue

            try:
                result_item = url_producer.get_result(timeout=0.1)
            except (TimeoutError, queue.Empty) as _:
                if not url_producer.has_pending_work():
                    # This consumer is saying that it doesn't have any
                    # pending or in progress work
                    finished.add(url_producer)
                    self._output.debug(
                        f"Producer {url_producer.get_name()} has finished (empty queue)"
                    )
            else:
                if result_item == POISON_PILL:
                    # This consumer is saying that it has finished, so we
                    # remove it from the list.
                    consumer_forced_end.add(url_producer)

                    msg = "Producer %s has finished (poison pill received, queue size: %s)"
                    args = (url_producer.get_name(), url_producer.out_queue.qsize())
                    self._output.debug(msg % args)

                elif isinstance(result_item, ExceptionData):
                    self._handle_consumer_exception(result_item)
                else:
                    *_unused, fuzzable_request_inst = result_item

                    for url_consumer in output:
                        url_consumer.in_queue_put(fuzzable_request_inst)

                    # This is rather complex to digest... so pay attention :)
                    #
                    # A consumer might be 100% idle (no tasks in input or
                    # output queues, no in progress work) and we still need
                    # to keep it alive, because output from another producer
                    # will be sent to that consumer and make it work again
                    #
                    # So, when one producer returns something, we set the
                    # finished list to empty in order to make them work again
                    finished = set()

        return finished, consumer_forced_end

    def _handle_all_consumer_exceptions(self, _other):
        """
        Get the exceptions raised by the consumers that do not return any
        data under normal circumstances, for example: grep and auth and handle
        them properly.
        """
        for other_consumer in _other:
            while True:
                try:
                    result_item = other_consumer.get_result_nowait()
                except queue.Empty:
                    break
                else:
                    if isinstance(result_item, ExceptionData):
                        self._handle_consumer_exception(result_item)

    def _handle_consumer_exception(self, exception_data):
        """
        Give proper handling to an exception that was raised by one of the
        consumers. Usually this means calling the ExceptionHandler which
        will decide what to do with it.

        Please note that ExtendedUrllib can raise a ScanMustStopByUserRequest
        which should get through this piece of code and be re-raised in order to
        reach the try/except clause in w3afCore's start.
        """
        self._w3af_core.exception_handler.handle_exception_data(exception_data)

    def _setup_crawl_infrastructure(self):
        """
        Setup the crawl and infrastructure consumer:
            * Retrieve all plugins from the core,
            * Create the consumer instance and more,
        """
        crawl_plugins = self._w3af_core.plugins.plugins["crawl"]
        infrastructure_plugins = self._w3af_core.plugins.plugins["infrastructure"]

        if crawl_plugins or infrastructure_plugins:
            discovery_plugins = infrastructure_plugins + crawl_plugins

            self._discovery_consumer = CrawlInfrastructure(
                discovery_plugins,
                self._w3af_core,
                cf.cf.get("max_discovery_time"),
                knowledge_base=self._knowledge_base,
                output=self._output,
            )
            self._discovery_consumer.start()

    def _setup_grep(self):
        """
        Setup the grep consumer:
            * Create a Queue,
            * Set the Queue in xurllib
            * Start the consumer
        """
        grep_plugins = self._w3af_core.plugins.plugins["grep"]

        if grep_plugins:
            self._grep_consumer = grep(
                grep_plugins, self._w3af_core, output=self._output
            )
            self._w3af_core.uri_opener.set_grep_queue_put(self._grep_consumer.grep)
            self._grep_consumer.start()

    def _teardown_grep(self):
        self._output.debug("Called strategy._teardown_grep()")

        if self._grep_consumer is not None:
            self._grep_consumer.join()
            self._grep_consumer = None

    def _teardown_audit(self):
        self._output.debug("Called strategy._teardown_audit()")

        if self._audit_consumer is not None:
            # Wait for all the in_queue items to get() from the queue
            self._audit_consumer.join()
            self._audit_consumer = None

    def _teardown_auth(self):
        self._output.debug("Called strategy._teardown_auth()")

        if self._auth_consumer is not None:
            self._auth_consumer.join()
            self._auth_consumer = None

    def _teardown_bruteforce(self):
        self._output.debug("Called strategy._teardown_bruteforce()")

        if self._bruteforce_consumer is not None:
            self._bruteforce_consumer.join()
            self._bruteforce_consumer = None

    def _teardown_crawl_infrastructure(self):
        self._output.debug("Called strategy._teardown_crawl_infrastructure()")

        if self._discovery_consumer is not None:
            self._discovery_consumer.join()
            self._discovery_consumer = None

    def _teardown_observers(self):
        self._output.debug("Called strategy._teardown_observers()")

        for observer in self._observers:
            observer.end()

    def _seed_discovery(self):
        """
        Create the first fuzzable request objects based on the targets and put
        them in the CrawlInfrastructure consumer Queue.

        This will start the whole discovery process, since plugins are going
        to consume from that Queue and then put their results in it again in
        order to continue discovering.
        """
        #
        #    GET the initial target URLs in order to save them
        #    in a list and use them as our bootstrap URLs
        #
        self._seed_producer.seed_output_queue(cf.cf.get("targets"))

    def _setup_bruteforce(self):
        """
        Create a bruteforce consumer instance with the bruteforce plugins
        and initialize it in order to start taking work from the input Queue.

        The input queue for this consumer is populated by the fuzzable request
        router.
        """
        bruteforce_plugins = self._w3af_core.plugins.plugins["bruteforce"]

        if bruteforce_plugins:
            self._bruteforce_consumer = bruteforce(
                bruteforce_plugins, self._w3af_core, output=self._output
            )
            self._bruteforce_consumer.start()

    def _setup_auth(self, timeout=5):
        """
        Start the thread that will make sure the xurllib always has a "fresh"
        session. The thread will call has_active_session() and login() for each enabled
        auth plugin every "timeout" seconds.
        """
        auth_plugins = self._w3af_core.plugins.plugins["auth"]

        if auth_plugins:
            self._auth_consumer = auth(
                auth_plugins, self._w3af_core, timeout, output=self._output
            )
            self._auth_consumer.start()
            self._auth_consumer.force_login()

    def _setup_audit(self):
        """
        Starts the audit plugin consumer
        """
        self._output.debug("Called _setup_audit()")

        audit_plugins = self._w3af_core.plugins.plugins["audit"]

        if audit_plugins:
            self._audit_consumer = audit(
                audit_plugins, self._w3af_core, output=self._output
            )
            self._audit_consumer.start()
