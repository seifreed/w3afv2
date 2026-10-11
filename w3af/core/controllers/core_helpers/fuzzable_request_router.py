"""Route discovery results between scan consumers."""

import queue
from multiprocessing import TimeoutError
from typing import Any, Protocol

from w3af.core.constants import POISON_PILL
from w3af.core.controllers.core_helpers.exception_handler import ExceptionData


class QueueLike(Protocol):
    def qsize(self) -> int: ...


class Consumer(Protocol):
    out_queue: QueueLike

    def get_name(self) -> str: ...

    def get_result(self, timeout: float = 0.5) -> Any: ...

    def get_result_nowait(self) -> Any: ...

    def has_pending_work(self) -> bool: ...

    def in_queue_put(self, work: Any) -> Any: ...


class ConsumerRuntime(Protocol):
    def get_seed_producer(self) -> Consumer: ...

    def get_discovery_consumer(self) -> Consumer | None: ...

    def get_bruteforce_consumer(self) -> Consumer | None: ...

    def get_audit_consumer(self) -> Consumer | None: ...

    def get_auth_consumer(self) -> Consumer | None: ...

    def get_grep_consumer(self) -> Consumer | None: ...


class WorkerPool(Protocol):
    def finish(self) -> None: ...


class ScanStatus(Protocol):
    def get_run_time(self) -> float: ...


class ScanExceptionHandler(Protocol):
    def handle_exception_data(self, exception_data: ExceptionData) -> None: ...


class ScanCore(Protocol):
    worker_pool: WorkerPool
    status: ScanStatus
    exception_handler: ScanExceptionHandler

    def stop(self) -> None: ...


class ScanConfiguration(Protocol):
    def get(self, name: str) -> Any: ...


class FuzzableRequestRouter:
    """Move fuzzable requests and consumer exceptions through one scan."""

    def __init__(
        self,
        core: ScanCore,
        consumer_runtime: ConsumerRuntime,
        output,
        configuration: ScanConfiguration,
    ) -> None:
        self._core = core
        self._consumer_runtime = consumer_runtime
        self._output = output
        self._configuration = configuration

    def route(self) -> None:
        """Route results until all producers have finished."""
        input_consumers = self._available_consumers(
            self._consumer_runtime.get_seed_producer(),
            self._consumer_runtime.get_discovery_consumer(),
            self._consumer_runtime.get_bruteforce_consumer(),
        )
        output_consumers = self._available_consumers(
            self._consumer_runtime.get_audit_consumer(),
            self._consumer_runtime.get_discovery_consumer(),
            self._consumer_runtime.get_bruteforce_consumer(),
        )
        exception_consumers = self._available_consumers(
            self._consumer_runtime.get_audit_consumer(),
            self._consumer_runtime.get_auth_consumer(),
            self._consumer_runtime.get_grep_consumer(),
        )

        finished: set[Consumer] = set()
        consumer_forced_end: set[Consumer] = set()

        while True:
            self._handle_all_consumer_exceptions(exception_consumers)
            route_result = self._route_one_batch(
                input_consumers,
                output_consumers,
                finished,
                consumer_forced_end,
            )

            if route_result is None:
                self._output.debug(
                    "The fuzzable request router loop will break."
                    " The scan will stop after all consumers complete"
                    " their teardown() process."
                )
                break

            finished, consumer_forced_end = route_result

            if self._scan_reached_max_time():
                msg = (
                    "The scan has reached the maximum scan time of %s minutes."
                    " The scan will end and some vulnerabilities might not be"
                    " identified."
                )
                self._output.information(msg % self._configuration.get("max_scan_time"))
                self._core.stop()
                break

    @staticmethod
    def _available_consumers(*consumers: Consumer | None) -> list[Consumer]:
        return [consumer for consumer in consumers if consumer is not None]

    def _scan_reached_max_time(self) -> bool:
        max_scan_time = self._configuration.get("max_scan_time")
        if max_scan_time == 0:
            return False

        return self._core.status.get_run_time() > max_scan_time

    def _route_one_batch(
        self,
        input_consumers: list[Consumer],
        output_consumers: list[Consumer],
        finished: set[Consumer],
        consumer_forced_end: set[Consumer],
    ) -> tuple[set[Consumer], set[Consumer]] | None:
        for producer in input_consumers:
            if len(input_consumers) == len(finished | consumer_forced_end):
                return None

            if producer in finished or producer in consumer_forced_end:
                continue

            try:
                result_item = producer.get_result(timeout=0.1)
            except (TimeoutError, queue.Empty):
                if not producer.has_pending_work():
                    finished.add(producer)
                    self._output.debug(
                        f"Producer {producer.get_name()} has finished (empty queue)"
                    )
            else:
                if result_item == POISON_PILL:
                    consumer_forced_end.add(producer)
                    msg = "Producer %s has finished (poison pill received, queue size: %s)"
                    self._output.debug(
                        msg % (producer.get_name(), producer.out_queue.qsize())
                    )
                elif isinstance(result_item, ExceptionData):
                    self._handle_consumer_exception(result_item)
                else:
                    *_unused, fuzzable_request = result_item
                    for consumer in output_consumers:
                        consumer.in_queue_put(fuzzable_request)
                    finished = set()

        return finished, consumer_forced_end

    def _handle_all_consumer_exceptions(self, consumers: list[Consumer]) -> None:
        for consumer in consumers:
            while True:
                try:
                    result_item = consumer.get_result_nowait()
                except queue.Empty:
                    break
                else:
                    if isinstance(result_item, ExceptionData):
                        self._handle_consumer_exception(result_item)

    def _handle_consumer_exception(self, exception_data: ExceptionData) -> None:
        self._core.exception_handler.handle_exception_data(exception_data)
