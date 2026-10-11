#
# Module providing the `ThreadPool` class for managing a thread pool
#
# multiprocessing/pool.py
#
# Copyright (c) 2006-2008, R Oudkerk
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
# 3. Neither the name of author nor the names of any contributors may be
#    used to endorse or promote products derived from this software
#    without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
# OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
# SUCH DAMAGE.
#

__all__ = ["ThreadPool"]

import collections
import itertools
import logging
import math
import threading
import time
from multiprocessing.util import debug

LOGGER = logging.getLogger(__name__)

#
# Constants representing the state of a pool
#

RUN = 0
CLOSE = 1
TERMINATE = 2

job_counter = itertools.count()


def mapstar(args):
    return list(map(*args))


def reraise(exception):
    raise exception


def guarded_task_generation(job, func, iterable):
    """
    Yield the tasks for running func on each item of iterable. When iterating
    the iterable fails, a last task which raises that exception in a worker
    is yielded, so the caller receives the error from the result object.
    """
    i = -1
    try:
        for i, item in enumerate(iterable):
            yield (job, i, func, (item,), {})
    except Exception as e:
        LOGGER.debug("Pool task iterable failed", exc_info=True)
        yield (job, i + 1, reraise, (e,), {})


class ThreadPool:
    """
    The pool operations and the internal handler threads.

    Subclasses create the queues, the worker threads and the handler threads.
    """

    def get_internal_thread_state(self):
        return {
            "worker_handler": self._worker_handler.is_alive(),
            "task_handler": self._task_handler.is_alive(),
            "result_handler": self._result_handler.is_alive(),
        }

    def get_pool_queue_sizes(self):
        return {
            "inqueue_size": self._inqueue.qsize(),
            "outqueue_size": self._outqueue.qsize(),
        }

    def _maintain_pool(self):
        """Clean up any exited workers and start replacements for them."""
        if self._join_exited_workers():
            self._repopulate_pool()

    def _check_running(self):
        if self._state != RUN:
            raise RuntimeError("Pool is not running")

    def apply(self, func, args=(), kwds=None):
        """
        Equivalent of `apply()` builtin
        """
        return self.apply_async(func, args, kwds).get()

    def map(self, func, iterable, chunksize=None):
        """
        Equivalent of `map()` builtin
        """
        return self.map_async(func, iterable, chunksize).get()

    def imap_unordered(self, func, iterable):
        """
        Like `map()` but lazy, and the ordering of results is arbitrary
        """
        self._check_running()
        result = IMapUnorderedIterator(self._cache)
        tasks = guarded_task_generation(result.job, func, iterable)
        self._taskqueue.put((tasks, result.set_length))
        return result

    def apply_async(self, func, args=(), kwds=None, callback=None):
        """
        Asynchronous equivalent of `apply()` builtin

        :param callback: Called with the return value of func when it succeeds
        """
        self._check_running()
        result = ApplyResult(self._cache, callback)
        task = (result.job, None, func, args, kwds or {})
        self._taskqueue.put(([task], None))
        return result

    def map_async(self, func, iterable, chunksize=None):
        """
        Asynchronous equivalent of `map()` builtin
        """
        self._check_running()
        if not hasattr(iterable, "__len__"):
            iterable = list(iterable)

        if chunksize is None:
            chunksize = math.ceil(len(iterable) / (len(self._pool) * 4))

        task_batches = ThreadPool._get_tasks(func, iterable, chunksize)
        result = MapResult(self._cache, chunksize, len(iterable))
        tasks = (
            (result.job, i, mapstar, (batch,), {})
            for i, batch in enumerate(task_batches)
        )
        self._taskqueue.put((tasks, None))
        return result

    @staticmethod
    def _handle_workers(pool):
        thread = threading.current_thread()

        # Keep maintaining workers until the cache gets drained, unless the pool
        # is terminated.
        while thread._state == RUN or (pool._cache and thread._state != TERMINATE):
            pool._maintain_pool()
            time.sleep(0.1)
        # send sentinel to stop workers
        pool._taskqueue.put(None)
        debug("worker handler exiting")

    @staticmethod
    def _handle_tasks(taskqueue, put, outqueue, pool):
        thread = threading.current_thread()

        for taskseq, set_length in iter(taskqueue.get, None):
            task = None
            for task in taskseq:
                if thread._state != RUN:
                    debug("task handler found thread._state != RUN")
                    break
                put(task)
            else:
                if set_length:
                    set_length(task[1] + 1 if task else 0)
                continue
            break
        else:
            debug("task handler got sentinel")

        # tell result handler to finish when cache is empty
        debug("task handler sending sentinel to result handler")
        outqueue.put(None)

        # tell workers there is no more work
        debug("task handler sending sentinel to workers")
        for _ in pool:
            put(None)

        debug("task handler exiting")

    @staticmethod
    def _handle_results(get, cache):
        thread = threading.current_thread()

        while True:
            task = get()

            if thread._state != RUN:
                debug("result handler found thread._state=TERMINATE")
                break

            if task is None:
                debug("result handler got sentinel")
                break

            job, i, obj = task
            if job in cache:
                cache[job].set(i, obj)

            # https://bugs.python.org/issue29861
            task = None
            obj = None

        debug("result handler exiting: len(cache)=%s", len(cache))

    @staticmethod
    def _get_tasks(func, it, size):
        it = iter(it)
        while True:
            x = tuple(itertools.islice(it, size))
            if not x:
                return
            yield (func, x)

    def close(self):
        debug("closing pool")
        if self._state == RUN:
            self._state = CLOSE
            self._worker_handler._state = CLOSE

    def terminate(self):
        debug("terminating pool")
        self._state = TERMINATE
        self._worker_handler._state = TERMINATE
        self._terminate()

    def join(self):
        debug("joining pool")
        if self._state == RUN:
            raise RuntimeError("Pool must be closing or terminating")
        self._worker_handler.join()
        self._task_handler.join()
        self._result_handler.join()
        for p in self._pool:
            p.join()

    def is_closed(self):
        return self._state in (CLOSE, TERMINATE)

    @staticmethod
    def _help_stuff_finish(inqueue, size):
        # put sentinels at head of inqueue to make workers finish
        with inqueue.not_empty:
            inqueue.queue.clear()
            inqueue.queue.extend([None] * size)
            inqueue.not_empty.notify_all()

    @classmethod
    def _terminate_pool(
        cls, inqueue, outqueue, pool, worker_handler, task_handler, result_handler
    ):
        # this is guaranteed to only be called once
        debug("finalizing pool")

        worker_handler._state = TERMINATE
        task_handler._state = TERMINATE

        debug("helping task handler/workers to finish")
        cls._help_stuff_finish(inqueue, len(pool))

        result_handler._state = TERMINATE
        outqueue.put(None)  # sentinel

        # We must wait for the worker handler to exit before terminating
        # workers because we don't want workers to be restarted behind our back.
        debug("joining worker handler")
        worker_handler.join()

        debug("joining task handler")
        task_handler.join()

        debug("joining result handler")
        result_handler.join()


class ApplyResult:
    """
    Class whose instances are returned by `ThreadPool.apply_async()`
    """

    def __init__(self, cache, callback=None):
        self._ready = threading.Event()
        self.job = next(job_counter)
        self._cache = cache
        self._callback = callback
        self._success = False
        self._value = None
        cache[self.job] = self

    def get(self):
        self._ready.wait()
        if self._success:
            return self._value
        raise self._value

    def _finish(self):
        del self._cache[self.job]
        self._ready.set()

    def set(self, i, obj):
        self._success, self._value = obj
        if self._callback and self._success:
            self._callback(self._value)
        self._finish()


class MapResult(ApplyResult):
    """
    Class whose instances are returned by `ThreadPool.map_async()`
    """

    def __init__(self, cache, chunksize, length):
        ApplyResult.__init__(self, cache)
        self._success = True
        self._value = [None] * length
        self._chunksize = chunksize
        self._number_left = math.ceil(length / chunksize) if length else 0
        if not self._number_left:
            self._finish()

    def set(self, i, obj):
        success, result = obj
        if not success:
            self._success = False
            self._value = result
            self._finish()
            return

        self._value[i * self._chunksize : (i + 1) * self._chunksize] = result
        self._number_left -= 1
        if self._number_left == 0:
            self._finish()


class IMapUnorderedIterator:
    """
    Class whose instances are returned by `ThreadPool.imap_unordered()`
    """

    def __init__(self, cache):
        self._cond = threading.Condition(threading.Lock())
        self.job = next(job_counter)
        self._cache = cache
        self._items = collections.deque()
        self._index = 0
        self._length = None
        cache[self.job] = self

    def __iter__(self):
        return self

    def __next__(self):
        with self._cond:
            while not self._items:
                if self._index == self._length:
                    raise StopIteration
                self._cond.wait()
            success, value = self._items.popleft()

        if success:
            return value
        self._discard_pending_results()
        raise value

    def _discard_pending_results(self):
        with self._cond:
            self._items.clear()
            self._cache.pop(self.job, None)

    def _remove_from_cache_when_done(self):
        if self._index == self._length:
            del self._cache[self.job]

    def set(self, i, obj):
        with self._cond:
            self._items.append(obj)
            self._index += 1
            self._cond.notify()
            self._remove_from_cache_when_done()

    def set_length(self, length):
        with self._cond:
            self._length = length
            self._cond.notify()
            self._remove_from_cache_when_done()
