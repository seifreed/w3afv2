"""
Worker-pool lifecycle for the scan controller.
"""

from w3af.core.controllers.threads.is_main_thread import is_main_thread
from w3af.core.controllers.threads.monkey_patch_debug import (
    monkey_patch_debug,
    remove_monkey_patch_debug,
)
from w3af.core.controllers.threads.threadpool import Pool


class WorkerPoolManager:
    """Create, replace, and terminate the core worker pool."""

    def __init__(self, output, processes, max_queued_tasks, maxtasksperchild):
        self._output = output
        self._processes = processes
        self._max_queued_tasks = max_queued_tasks
        self._maxtasksperchild = maxtasksperchild
        self._pool = None

    def get_pool(self):
        if self._pool is None:
            self._pool = self._create_pool()
            self._output.debug(
                f"Created first Worker pool for core (id: {id(self._pool)})"
            )
            return self._pool

        if self._pool.is_running():
            return self._pool

        old_pool_id = id(self._pool)
        if is_main_thread():
            self._pool.terminate_join()

        self._pool = self._create_pool()
        msg = (
            "Created a new worker pool for core (id: %s) because the old"
            " one was not in running state (id: %s)"
        )
        self._output.debug(msg % (id(self._pool), old_pool_id))
        return self._pool

    def terminate(self):
        self._output.debug("Called _terminate_worker_pool()")
        monkey_patch_debug(self._output)
        try:
            self.get_pool().terminate_join()
        finally:
            remove_monkey_patch_debug()

    def _create_pool(self):
        return Pool(
            processes=self._processes,
            worker_names="WorkerThread",
            max_queued_tasks=self._max_queued_tasks,
            maxtasksperchild=self._maxtasksperchild,
        )
