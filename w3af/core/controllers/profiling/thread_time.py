"""
thread_time.py

Copyright 2018 Andres Riancho

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

import time

"""
Retrieve per-thread CPU time.

Definition of thread CPU time:
    > The amount of time the CPU spent on the given thread.

The thread could be in three states:
   #1 Waiting for IO (network, fs, etc)
   #2 IDLE (kernel paused the thread)
   #3 Running thread code (consuming CPU cycles)
   #4 Running kernel code associated with the thread (consuming CPU cycles)

thread_active_time() returns (#3 + #4).

time.thread_time() is clock_gettime(CLOCK_THREAD_CPUTIME_ID) and is available
on Linux, macOS and Windows, so it replaces the old Linux-only getrusage()
implementation and works on every platform w3af supports.
"""

__all__ = ("thread_active_time",)

thread_active_time = time.thread_time
