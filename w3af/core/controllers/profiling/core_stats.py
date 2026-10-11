"""
core_stats.py

Copyright 2014 Andres Riancho

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

import json
import logging
import os
import sys
import tempfile
import threading
import traceback
from functools import partial

from w3af.core.profiling import is_core_profiling_enabled

from .utils import cancel_thread, dump_data_every_thread, get_filename_fmt

PROFILING_OUTPUT_FMT = os.path.join(tempfile.gettempdir(), "w3af-%s-%s.core")
DELAY_MINUTES = 2
SAVE_THREAD_PTR: list[threading.Timer] = []


def should_profile_core(wrapped):
    def inner(w3af_core, output_manager):
        if is_core_profiling_enabled():
            return wrapped(w3af_core, output_manager)

    return inner


@should_profile_core
def start_core_profiling(w3af_core, output_manager):
    """
    If the environment variable W3AF_PROFILING is set to 1, then we start
    the CPU and memory profiling.

    :return: None
    """
    dd_partial = partial(dump_data, w3af_core, output_manager)
    dump_data_every_thread(dd_partial, DELAY_MINUTES, SAVE_THREAD_PTR)


def dump_data(w3af_core, output_manager):
    s = w3af_core.status
    try:
        data = {
            "Requests sent": s.get_sent_request_count(),
            "Requests per minute": s.get_rpm(),
            "Crawl input queue input speed": s.get_crawl_input_speed(),
            "Crawl input queue output speed": s.get_crawl_output_speed(),
            "Crawl input queue size": s.get_crawl_qsize(),
            "Crawl output queue size": s.get_crawl_output_qsize(),
            "Audit input queue input speed": s.get_audit_input_speed(),
            "Audit input queue output speed": s.get_audit_output_speed(),
            "Audit input queue size": s.get_audit_qsize(),
            "Grep input queue size": s.get_audit_qsize(),
            "Core worker pool input queue size": s.get_core_worker_pool_queue_size(),
            "Output manager input queue size": get_queue_size(
                output_manager.get_in_queue()
            ),
            "Cache stats": get_parser_cache_stats(w3af_core.parser_cache),
        }
    except Exception as e:
        logging.getLogger(__name__).debug("Failed to collect core stats", exc_info=True)
        exc_type, exc_value, exc_tb = sys.exc_info()
        tback = traceback.format_exception(exc_type, exc_value, exc_tb)

        data = {"Exception": str(e), "Traceback": tback}

    json_data = json.dumps(data, indent=4)
    output_file = PROFILING_OUTPUT_FMT % get_filename_fmt()
    with open(output_file, "w") as output_fh:
        output_fh.write(json_data)


@should_profile_core
def stop_core_profiling(w3af_core, output_manager):
    """
    Save profiling information (if available)
    """
    cancel_thread(SAVE_THREAD_PTR)
    dump_data(w3af_core, output_manager)


def get_queue_size(queue):
    """
    :return: The queue size, None in platforms where it is not implemented
             for multiprocessing queues (for example macOS)
    """
    try:
        return queue.qsize()
    except NotImplementedError:
        return None


def get_parser_cache_stats(parser_cache):
    r = {
        "hit_rate": parser_cache.get_hit_rate(),
        "max_lru_items": parser_cache.get_max_lru_items(),
        "current_lru_size": parser_cache.get_current_lru_items(),
        "total_cache_queries": parser_cache.get_total_queries(),
        "do_not_cache": parser_cache.get_do_not_cache(),
    }

    worker_size, queue_size = parser_cache.get_pool_stats()
    r["Parser pool worker size"] = worker_size
    r["Parser pool input queue size"] = queue_size

    return r
