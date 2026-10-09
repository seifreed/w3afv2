"""
cpu_usage.py

Copyright 2012 Andres Riancho

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

import threading

from w3af.core.profiling import is_cpu_profiling_enabled

from .utils import cancel_thread, dump_data_every_thread, get_filename_fmt

PROFILING_OUTPUT_FMT = "/tmp/w3af-%s-%s.cpu"
DELAY_MINUTES = 2
SAVE_THREAD_PTR: list[threading.Timer] = []


def should_profile_cpu(wrapped):
    def inner():
        if is_cpu_profiling_enabled():
            return wrapped()

    return inner


@should_profile_cpu
def start_cpu_profiling():
    """
    If the environment variable W3AF_PROFILING is set to 1, then we start
    the CPU and memory profiling.

    :return: None
    """
    import yappi

    yappi.start()

    dump_data_every_thread(dump_data, DELAY_MINUTES, SAVE_THREAD_PTR)


def dump_data():
    import yappi

    # pylint: disable=E1101
    yappi.get_func_stats().save(PROFILING_OUTPUT_FMT % get_filename_fmt(), type="pstat")
    # pylint: enable=E1101


@should_profile_cpu
def stop_cpu_profiling():
    """
    Save profiling information (if available)
    """
    cancel_thread(SAVE_THREAD_PTR)
    dump_data()
