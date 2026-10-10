"""
psutil_stats.py

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

import json
import os
import tempfile
import threading

import psutil

from .utils import cancel_thread, dump_data_every_thread, get_filename_fmt

PROFILING_OUTPUT_FMT = os.path.join(tempfile.gettempdir(), "w3af-%s-%s.psutil")
DELAY_MINUTES = 2
SAVE_PSUTIL_PTR: list[threading.Timer] = []

PROCESS_ATTRIBUTES = (
    "pid",
    "name",
    "ppid",
    "status",
    "io_counters",
    "num_threads",
    "cpu_times",
    "cpu_percent",
    "memory_info",
    "memory_percent",
    "exe",
    "cmdline",
)


def user_wants_psutil():
    _should_profile = os.environ.get("W3AF_PSUTILS", "0")

    return bool(_should_profile.isdigit() and int(_should_profile) == 1)


def should_dump_psutil(wrapped):
    def inner():
        if user_wants_psutil():
            return wrapped()

    return inner


@should_dump_psutil
def start_psutil_dump():
    """
    If the environment variable W3AF_PSUTILS is set to 1, then we start
    the thread that will dump the operating system data which can be retrieved
    using psutil module.

    :return: None
    """
    dump_data_every_thread(dump_psutil, DELAY_MINUTES, SAVE_PSUTIL_PTR)


def as_plain_data(value):
    """
    :return: A dict for named tuples (psutil's result type), anything else
             is returned untouched
    """
    if hasattr(value, "_asdict"):
        return dict(value._asdict())

    return value


def get_processes_info():
    """
    :return: A dict with the pid as key and the attributes psutil supports in
             this platform as values
    """
    attributes = [name for name in PROCESS_ATTRIBUTES if hasattr(psutil.Process, name)]
    process_info = {}

    for proc in psutil.process_iter(attrs=attributes):
        pinfo = {name: as_plain_data(value) for name, value in proc.info.items()}
        process_info[pinfo["pid"]] = pinfo

    return process_info


def get_process_memory(proc):
    """
    :param proc: A psutil.Process instance
    :return: The memory used by the process, None if it does not exist anymore
    """
    try:
        memory = proc.memory_info()
        command_line = " ".join(proc.cmdline())
    except psutil.NoSuchProcess:
        return None

    return {
        "RSS": memory.rss,
        "VMS": memory.vms,
        "Command line": command_line,
    }


def get_memory_usage():
    """
    :return: The memory used by this process and all its children
    """
    current = psutil.Process()
    processes = [current, *current.children(recursive=True)]
    usage = [get_process_memory(proc) for proc in processes]

    return [memory for memory in usage if memory is not None]


def dump_psutil():
    """
    Dumps operating system information to file
    """
    output_file = PROFILING_OUTPUT_FMT % get_filename_fmt()

    netinfo = {
        nic: as_plain_data(counters)
        for nic, counters in psutil.net_io_counters(pernic=True).items()
    }

    du_data = psutil.disk_usage(tempfile.gettempdir())
    disk_usage = {
        "total": get_human_readable_size(du_data.total),
        "free": get_human_readable_size(du_data.free),
        "% used": du_data.percent,
    }

    # Merge all the data here
    psutil_data = {
        "CPU": as_plain_data(psutil.cpu_times()),
        "Load average": psutil.getloadavg(),
        "Virtual memory": as_plain_data(psutil.virtual_memory()),
        "Swap memory": as_plain_data(psutil.swap_memory()),
        "Network": netinfo,
        "Processes": get_processes_info(),
        "Process memory": get_memory_usage(),
        "Disk IO counters": as_plain_data(psutil.disk_io_counters()),
        "Disk usage": disk_usage,
        "Thread CPU usage": get_threads_cpu_percent(),
    }

    with open(output_file, "w") as output_fh:
        json.dump(psutil_data, output_fh, indent=4, sort_keys=True)


def get_threads_cpu_percent(interval=0.1):
    proc = psutil.Process()

    total_percent = proc.cpu_percent(interval=interval)

    process_times = proc.cpu_times()
    total_time = process_times.user + process_times.system

    result = {}
    for thread in proc.threads():
        thread_time = thread.system_time + thread.user_time
        thread_percent = total_percent * (thread_time / total_time)
        result[thread.id] = {
            "Thread total time": thread_time,
            "Thread CPU usage %": thread_percent,
        }

    return result


@should_dump_psutil
def stop_psutil_dump():
    """
    Save profiling information (if available)
    """
    cancel_thread(SAVE_PSUTIL_PTR)
    dump_psutil()


def get_human_readable_size(num):
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    value = float(num)
    i = 0
    while value >= 1024 and i + 1 < len(units):
        value /= 1024
        i += 1

    return f"{int(value)} {units[i]}"
