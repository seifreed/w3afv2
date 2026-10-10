"""
Queue metrics exposed to scan status.
"""

from w3af.core.controllers.core_helpers.status_eta import AUDIT, CRAWL, GREP


class ConsumerMetrics:
    """Read consumer and worker-pool metrics without owning the core."""

    def __init__(self, strategy=None, worker_pool_provider=None):
        self._strategy = strategy
        self._worker_pool_provider = worker_pool_provider

    def set_dependencies(self, strategy, worker_pool_provider):
        self._strategy = strategy
        self._worker_pool_provider = worker_pool_provider

    def _get_consumer(self, phase):
        if self._strategy is None:
            return None

        getter_names = {
            CRAWL: "get_discovery_consumer",
            AUDIT: "get_audit_consumer",
            GREP: "get_grep_consumer",
        }
        return getattr(self._strategy, getter_names[phase])()

    def get_input_speed(self, phase):
        consumer = self._get_consumer(phase)
        return 0 if consumer is None else consumer.in_queue.get_input_rpm()

    def get_output_speed(self, phase):
        consumer = self._get_consumer(phase)
        return 0 if consumer is None else consumer.in_queue.get_output_rpm()

    def get_queue_size(self, phase):
        consumer = self._get_consumer(phase)
        if consumer is None:
            return 0

        return consumer.get_running_task_count() + consumer.in_queue.qsize()

    def get_output_queue_size(self, phase):
        consumer = self._get_consumer(phase)
        return 0 if consumer is None else consumer.out_queue.qsize()

    def get_processed_tasks(self, phase):
        consumer = self._get_consumer(phase)
        if consumer is None:
            return None if phase == GREP else 0

        queue = consumer.out_queue if phase == CRAWL else consumer.in_queue
        return queue.get_processed_tasks()

    def has_finished(self, phase):
        consumer = self._get_consumer(phase)
        return True if consumer is None else consumer.has_finished()

    def get_worker_pool_queue_size(self):
        if self._worker_pool_provider is None:
            return 0

        return self._worker_pool_provider().get_inqueue().qsize()
