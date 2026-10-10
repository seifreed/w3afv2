"""
exec_methodHelpers.py

Copyright 2006 Andres Riancho

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

import posixpath

from w3af.core.data.fuzzer.utils import rand_alnum
from w3af.core.exceptions import BaseFrameworkException

# Temporary directory on the *remote* Linux target being exploited, not a path
# on the machine running w3af.
REMOTE_LINUX_TEMP_DIR = posixpath.join(posixpath.sep, "tmp")


def os_detection_exec(exec_method, output):
    """
    Uses the exec_method to run remote commands and determine what's the
    remote OS is and returns a string with 'windows' or 'linux' or raises
    a BaseFrameworkException if unknown.
    """
    try:
        linux1 = exec_method("echo -n w3af")
        linux2 = exec_method("head -n 1 /etc/passwd")
    except BaseFrameworkException:
        pass
    else:
        if "w3af" in linux1 and linux2.count(":") > 3:
            output.debug('Identified remote OS as Linux, returning "linux".')
            return "linux"

    try:
        # Try if it's a windows system
        win1 = exec_method("type %SYSTEMROOT%\\win.ini")
        win2 = exec_method("echo /?")
    except BaseFrameworkException:
        pass
    else:
        if "[fonts]" in win1 and "ECHO" in win2:
            output.debug('Identified remote OS as Windows, returning "windows".')
            return "windows"

    raise BaseFrameworkException("Failed to get/identify the remote OS.")


def get_remote_temp_file(exec_method, output):
    """
    :return: The name of a file in the remote file system that the user that I'm
             executing commands with can write, read and execute. The normal
             responses for this are files in /tmp/ or %TEMP% depending on the
             remote OS.
    """
    os = os_detection_exec(exec_method, output)
    if os == "windows":
        _filename = exec_method("echo %TEMP%").strip() + "\\"
        _filename += rand_alnum(6)

        # verify exists
        dir_res = exec_method("dir " + _filename).strip().lower()
        if "not found" in dir_res:
            return _filename
        else:
            # Shit, the file exists, run again and see what we can do
            return get_remote_temp_file(exec_method, output)

        return _filename

    elif os == "linux":
        _filename = posixpath.join(REMOTE_LINUX_TEMP_DIR, rand_alnum(6))

        # verify exists
        ls_res = exec_method("ls " + _filename).strip()
        if "No such file" in ls_res:
            return _filename
        else:
            # Shit, the file exists, run again and see what we can do
            return get_remote_temp_file(exec_method, output)

    else:
        msg = "Failed to create filename for a temporary file in the remote host."
        raise BaseFrameworkException(msg)
