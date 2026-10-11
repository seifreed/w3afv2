"""
pytracemalloc.py

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

import gc
import os
import tempfile
import threading
import tracemalloc

from w3af.core.data.misc.serialize import dump
from w3af.core.profiling import is_tracemalloc_enabled

from .utils import cancel_thread, dump_data_every_thread, get_filename_fmt

PROFILING_OUTPUT_FMT = os.path.join(tempfile.gettempdir(), "w3af-%s-%s.tracemalloc")
DELAY_MINUTES = 2
SAVE_TRACEMALLOC_PTR: list[threading.Timer] = []


def should_dump_tracemalloc(wrapped):
    def inner():
        if is_tracemalloc_enabled():
            return wrapped()

    return inner


@should_dump_tracemalloc
def start_tracemalloc_dump():
    """
    If the environment variable W3AF_PYTRACEMALLOC is set to 1, then we start
    the thread that will dump the memory usage data which can be retrieved
    using tracemalloc module.

    :return: None
    """
    # save 25 frames
    tracemalloc.start(25)

    dump_data_every_thread(dump_tracemalloc, DELAY_MINUTES, SAVE_TRACEMALLOC_PTR)


def dump_tracemalloc():
    """
    Dumps memory usage information to file
    """
    gc.collect()
    snapshot = tracemalloc.take_snapshot()

    output_file = PROFILING_OUTPUT_FMT % get_filename_fmt()
    with open(output_file, "wb") as fp:
        dump(snapshot, fp, 2)

    # Make sure the snapshot goes away before the next scheduled dump.
    del snapshot


@should_dump_tracemalloc
def stop_tracemalloc_dump():
    """
    Save profiling information (if available)
    """
    cancel_thread(SAVE_TRACEMALLOC_PTR)
    dump_tracemalloc()
