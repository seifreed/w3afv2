"""
__init__.py

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

import logging

from .core_stats import start_core_profiling, stop_core_profiling
from .cpu_usage import start_cpu_profiling, stop_cpu_profiling
from .processes import start_process_dump, stop_process_dump
from .psutil_stats import start_psutil_dump, stop_psutil_dump
from .pytracemalloc import start_tracemalloc_dump, stop_tracemalloc_dump
from .thread_activity import start_thread_stack_dump, stop_thread_stack_dump


def start_profiling(w3af_core, output, output_manager):
    core_save_thread_ptr = start_core_profiling(w3af_core, output_manager) or []
    start_profiling_no_core()
    return core_save_thread_ptr


def start_profiling_no_core():
    start_cpu_profiling()
    start_thread_stack_dump()
    start_process_dump()
    start_psutil_dump()
    start_tracemalloc_dump()


def stop_profiling(w3af_core, output, output_manager, core_save_thread_ptr=None):
    output.debug("Called stop_profiling()")

    try:
        if w3af_core is not None:
            stop_core_profiling(w3af_core, output_manager, core_save_thread_ptr or [])
        stop_profiling_no_core()
    except Exception as e:
        output.debug(f'Call to stop_profiling() failed with: "{e}"')
        logging.getLogger(__name__).debug("stop_profiling() failed", exc_info=True)


def stop_profiling_no_core():
    stop_cpu_profiling()
    stop_thread_stack_dump()
    stop_process_dump()
    stop_psutil_dump()
    stop_tracemalloc_dump()
