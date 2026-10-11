"""
mp_document_parser.py

Copyright 2015 Andres Riancho

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
import multiprocessing
import os
import resource
import signal
import threading
from concurrent.futures import TimeoutError

import psutil
from pebble import ProcessPool
from pebble.common import ProcessExpired
from tblib.decorators import Error, return_error

from w3af.core.data.parsers.document_parser import DocumentParser
from w3af.core.data.parsers.ipc.serialization import (
    load_http_response_from_temp_file,
    load_object_from_temp_file,
    load_tags_from_temp_file,
    remove_file_if_exists,
    write_http_response_to_temp_file,
    write_object_to_temp_file,
    write_tags_to_temp_file,
)
from w3af.core.environment import is_running_on_ci
from w3af.core.exceptions import ScanMustStopException
from w3af.core.profiling import (
    is_core_profiling_enabled,
    is_cpu_profiling_enabled,
    is_memory_profiling_enabled,
    is_tracemalloc_enabled,
)

LOGGER = logging.getLogger(__name__)


@return_error
def apply_with_return_error(args):
    """
    :see: https://github.com/ionelmc/python-tblib/issues/4
    """
    return args[0](*args[1:])


# 128 MB
DEFAULT_MEMORY_LIMIT = 128 * 1024 * 1024


def get_memory_limit():
    env_memory_limit = os.environ.get("PARSER_MEMORY_LIMIT", "")

    if env_memory_limit.isdigit():
        msg = "Using parser process virtual memory limit of %s bytes that was defined in env."
        print(msg % env_memory_limit)
        return int(env_memory_limit)

    return DEFAULT_MEMORY_LIMIT


class DocumentParsingError(Exception):
    """Raised when the parser sub-process fails to handle a document."""


class ParserMemoryLimitError(MemoryError):
    """Raised when a parser sub-process exceeds its memory usage limit."""


class MultiProcessingDocumentParser:
    """
    A document parser that performs all it's tasks in different processes and
    returns results to the main process.

    Also implements a parsing timeout just in case the parser enters an infinite
    loop.

    :author: Andres Riancho (andres.riancho@gmail.com)
    """

    DEBUG = is_core_profiling_enabled()
    MAX_WORKERS = (
        2 if is_running_on_ci() else min(max(multiprocessing.cpu_count() // 2, 1), 2)
    )

    # Increasing the timeout when profiling is enabled seems to fix issue #9713
    #
    # https://github.com/andresriancho/w3af/issues/9713
    PROFILING_ENABLED = (
        is_memory_profiling_enabled()
        or is_tracemalloc_enabled()
        or is_cpu_profiling_enabled()
    )

    # in seconds
    PARSER_TIMEOUT = 60 * 3 if PROFILING_ENABLED else 10

    # Document parsers can go crazy on memory usage when parsing some very
    # specific HTML / PDF documents. Sometimes when this happens the operating
    # system does an out of memory (OOM) kill of a "randomly chosen" process.
    #
    # We limit the memory which can be used by parsing processes to this constant
    #
    # The feature was tested in test_pebble_limit_memory_usage.py
    MEMORY_LIMIT = get_memory_limit()

    def __init__(
        self,
        parser_timeout=PARSER_TIMEOUT,
        max_workers=MAX_WORKERS,
        memory_limit=MEMORY_LIMIT,
        parsers=DocumentParser.PARSERS,
        log_queue_provider=None,
        worker_initializer=None,
    ):
        """
        :param parser_timeout: Seconds a worker may spend on one document
        :param max_workers: Number of worker processes in the pool
        :param memory_limit: Bytes each worker may allocate on top of the
                             memory it uses when it starts
        :param parsers: Parser classes tried, in order, for each document
        """
        self.parser_timeout = parser_timeout
        self.max_workers = max_workers
        self.memory_limit = memory_limit
        self.parsers = parsers
        self.log_queue_provider = log_queue_provider
        self.worker_initializer = worker_initializer
        self._pool: ProcessPool | None = None
        self._start_lock = threading.RLock()

    def start_workers(self):
        """
        Start the pool and workers
        :return: The pool instance
        """
        with self._start_lock:
            if self._pool is None:

                # Start the process pool
                log_queue = (
                    self.log_queue_provider() if self.log_queue_provider else None
                )
                self._pool = ProcessPool(
                    self.max_workers,
                    max_tasks=20,
                    initializer=init_worker,
                    initargs=(self.worker_initializer, log_queue, self.memory_limit),
                )

        return self._get_pool()

    def _get_pool(self) -> ProcessPool:
        pool = self._pool
        if pool is None:
            raise RuntimeError("Parser worker pool has not been started")
        return pool

    def stop_workers(self):
        """
        Stop the pool workers
        :return: None
        """
        if self._pool is not None:
            self._pool.stop()
            self._pool.join()
            self._pool = None

    def get_pool_stats(self):
        """Return worker and input queue sizes for the owned parser pool."""
        if self._pool is None:
            return 0, 0

        try:
            queue_size = self._pool._context.task_queue.qsize()
        except NotImplementedError:
            queue_size = None

        return (
            self._pool._context.workers,
            queue_size,
        )

    def get_document_parser_for(self, http_response):
        """
        Get a document parser for http_response

        This parses the http_response in a pool worker. This method has two
        features:
            * We can kill the worker if the parser is taking too long
            * We can have different parsers

        :param http_response: The http response instance
        :return: An instance of DocumentParser
        """
        # Start the worker processes if needed
        self.start_workers()

        filename = write_http_response_to_temp_file(http_response)

        apply_args = (process_document_parser, filename, self.DEBUG, self.parsers)

        # Push the task to the workers
        pool = self._get_pool()
        try:
            future = pool.schedule(
                apply_with_return_error, args=(apply_args,), timeout=self.parser_timeout
            )
        except RuntimeError as rte:
            # Remove the temp file used to send data to the process
            remove_file_if_exists(filename)

            # We get here when the pebble pool management thread dies and
            # suddenly starts answering all calls with:
            #
            # RuntimeError('Unexpected error within the Pool')
            #
            # The scan needs to stop because we can't parse any more
            # HTTP responses, which is a very critical part of the process
            msg = str(rte)
            raise ScanMustStopException(msg)

        try:
            process_result = future.result()
        except TimeoutError:
            msg = (
                "[timeout] The parser took more than %s seconds"
                ' to complete parsing of "%s", killed it!'
            )
            args = (self.parser_timeout, http_response.get_url())
            raise TimeoutError(msg % args)
        except ProcessExpired:
            # We reach here when the process died because of an error, we
            # handle this just like when the parser takes a lot of time and
            # we're unable to retrieve an answer from it
            msg = (
                "One of the parser processes died unexpectedly, this could"
                " be because of a bug, the operating system triggering OOM"
                " kills, etc. The scanner will continue with the next"
                " document, but the scan results might be inconsistent."
            )
            raise TimeoutError(msg)
        finally:
            # Remove the temp file used to send data to the process, we already
            # have the result, so this file is not needed anymore
            remove_file_if_exists(filename)

        # We still need to perform some error handling here...
        if isinstance(process_result, Error):
            if isinstance(process_result.exc_value, MemoryError):
                msg = (
                    "The parser exceeded the memory usage limit of %s bytes"
                    ' while trying to parse "%s". The parser was stopped in'
                    " order to prevent OOM issues."
                )
                args = (self.memory_limit, http_response.get_url())
                LOGGER.debug(msg % args)
                raise ParserMemoryLimitError(msg % args)

            raise_parsing_error(process_result)

        return load_object_from_temp_file(process_result)

    def get_tags_by_filter(self, http_response, tags, yield_text=False):
        """
        Return Tag instances for the tags which match the `tags` filter,
        parsing and all lxml stuff is done in another process and the Tag
        instances are sent to the main process (the one calling this method)
        through a pipe

        Some things to note:
            * Not all responses can be parsed, so I need to call DocumentParser
              and handle exceptions

            * The parser selected by DocumentParser might not have tags, and
              it might not have get_tags_by_filter. In this case just return an
              empty list

            * Just like get_document_parser_for we have a timeout in place,
              when we hit the timeout just return an empty list, this is not
              the best thing to do, but makes the plugin code easier to write
              (plugins would ignore this anyways)

        :param tags: The filter
        :param yield_text: Should we yield the tag text?
        :return: A list of Tag instances as defined in sgml.py

        :see: SGMLParser.get_tags_by_filter
        """
        # Start the worker processes if needed
        self.start_workers()

        filename = write_http_response_to_temp_file(http_response)

        apply_args = (
            process_get_tags_by_filter,
            filename,
            tags,
            yield_text,
            self.DEBUG,
            self.parsers,
        )

        #
        # Push the task to the workers
        #
        pool = self._get_pool()
        try:
            future = pool.schedule(
                apply_with_return_error, args=(apply_args,), timeout=self.parser_timeout
            )
        except RuntimeError as rte:
            # Remove the temp file used to send data to the process
            remove_file_if_exists(filename)

            # We get here when the pebble pool management thread dies and
            # suddenly starts answering all calls with:
            #
            # RuntimeError('Unexpected error within the Pool')
            #
            # The scan needs to stop because we can't parse any more
            # HTTP responses, which is a very critical part of the process
            msg = str(rte)
            raise ScanMustStopException(msg)

        try:
            process_result = future.result()
        except TimeoutError:
            # We hit a timeout, return an empty list
            return []
        except ProcessExpired:
            # We reach here when the process died because of an error
            return []
        finally:
            # Remove the temp file used to send data to the process
            remove_file_if_exists(filename)

        # There was an exception in the parser, maybe the HTML was really
        # broken, or it wasn't an HTML at all.
        if isinstance(process_result, Error):
            if isinstance(process_result.exc_value, MemoryError):
                msg = (
                    "The parser exceeded the memory usage limit of %s bytes"
                    ' while trying to parse "%s". The parser was stopped in'
                    " order to prevent OOM issues."
                )
                args = (self.memory_limit, http_response.get_url())
                LOGGER.debug(msg % args)

            return []

        return load_tags_from_temp_file(process_result)


def raise_parsing_error(process_result):
    """
    Re-raise the exception captured in the parser sub-process wrapped in a
    DocumentParsingError, keeping the original exception and traceback chained.
    """
    error = process_result.exc_value.with_traceback(process_result.traceback)
    raise DocumentParsingError(str(error)) from error


def process_get_tags_by_filter(filename, tags, yield_text, debug, parsers):
    """
    Parse the HTTP response stored in filename and write the tags matching the
    filter to a temp file.
    """
    http_resp = load_http_response_from_temp_file(filename)

    document_parser = DocumentParser(http_resp, parsers)
    parser = document_parser.get_parser()

    # Not all parsers have tags
    if not hasattr(parser, "get_tags_by_filter"):
        return write_tags_to_temp_file([])

    filtered_tags = list(parser.get_tags_by_filter(tags, yield_text=yield_text))

    msg = (
        "Returned %s Tag instances at get_tags_by_filter() for URL %s"
        " and tags filter %r"
    )
    args = (len(filtered_tags), http_resp.get_uri(), tags)
    LOGGER.debug(msg % args)

    result_filename = write_tags_to_temp_file(filtered_tags)

    return result_filename


def process_document_parser(filename, debug, parsers):
    """
    Parse the HTTP response stored in filename and write the resulting
    DocumentParser to a temp file.
    """
    http_resp = load_http_response_from_temp_file(filename)
    pid = multiprocessing.current_process().pid

    if debug:
        msg = "[mp_document_parser] PID %s is starting to parse %s"
        args = (pid, http_resp.get_url())
        LOGGER.debug(msg % args)

    try:
        # Parse
        document_parser = DocumentParser(http_resp, parsers)
    except Exception as e:
        if debug:
            msg = (
                "[mp_document_parser] PID %s finished parsing %s with"
                ' exception: "%s"'
            )
            error_args = (pid, http_resp.get_url(), e)
            LOGGER.debug(msg % error_args)
        raise
    else:
        if debug:
            msg = (
                "[mp_document_parser] PID %s finished parsing %s without any"
                " exception"
            )
            args = (pid, http_resp.get_url())
            LOGGER.debug(msg % args)

    result_filename = write_object_to_temp_file(document_parser)

    return result_filename


def init_worker(worker_initializer, log_queue, mem_limit):
    """
    This function is called right after each Process in the ProcessPool is
    created, and it will initialized some variables/handlers which are required
    for it to work as expected

    :return: None
    """
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    if worker_initializer is not None:
        worker_initializer(log_queue)
    limit_memory_usage(mem_limit)


RLIMIT_AS = getattr(resource, "RLIMIT_AS", None)


def limit_memory_usage(mem_limit, rlimit=RLIMIT_AS):
    """
    Set the soft memory limit for the worker process.

    Retrieve current limits, re-use the hard limit.

    See documentation on resources at:
        https://linux.die.net/man/2/getrlimit

    Not available:
        RLIMIT_RSS is not available for new kernel versions

    Could work:
        RLIMIT_AS The maximum size of the process's virtual memory
                  (address space) in bytes.

                  Reminder of how virtual memory works:
                  https://en.wikipedia.org/wiki/Virtual_memory

        RLIMIT_STACK The maximum size of the process stack, in bytes.
        RLIMIT_DATA The maximum size of the process's data segment
                    (initialized data, uninitialized data, and heap)

    Not sure:
        RLIMIT_MEMLOCK The maximum number of bytes of memory that may
        be locked into RAM
    """
    if rlimit is None:
        print(
            "w3af was unable to limit the memory usage of parser processes."
            " This feature is only supported in Linux OS, create an issue"
            " in our repository and we might implement it for your OS."
        )
        return

    # Note that this is run on every process start, which is what we need
    #
    # Since the real memory limit will be w3af's main process memory usage
    # plus the imposed memory limit (mem_limit) we want to calculate this
    # as often as possible.
    #
    # New processes are created in the pool after 20 jobs (max_tasks=20) so
    # that should take care of cycling processes with different real memory
    # limits
    real_memory_limit = psutil.Process().memory_info().vms + mem_limit

    _soft, hard = resource.getrlimit(rlimit)
    resource.setrlimit(rlimit, (real_memory_limit, hard))

    limit_mb = real_memory_limit / 1024 / 1024
    msg = "Using RLIMIT_AS memory usage limit %s MB for new pool process"
    LOGGER.debug(msg % limit_mb)
