"""
file_utils.py

Copyright 2008 Andres Riancho

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

import shlex
import string
from datetime import datetime

from git.cmd import Git, GitCommandError

from w3af.core.data.misc.local_date import local_today

ALLOWED = string.digits + string.ascii_letters + "/.-_"


def replace_file_special_chars(filename_path):
    """This is a *very* incomplete function which I added to fix a bug:
    http://sourceforge.net/apps/trac/w3af/ticket/173308

    And after realizing that it was very hard to perform a replace
    that worked for all platforms and when the thing to sanitize was a
    path+filename and not only a filename."""
    return filename_path.replace(":", "_")


def days_since_file_update(path, days):
    """
    :return: True if the filename was updated earlier than @days before today
    """
    time_delta_days = get_days_since_last_update(path)
    return time_delta_days > days


def get_days_since_last_update(path):
    """
    :return: The days since the last update of any of the files in path. If the
             path points to a filename, the last update of that filename is
             returned.
    """
    git = Git(".")
    cmd_str = f"git log -1 --format=%cd {path}"
    cmd = shlex.split(cmd_str)

    try:
        date_str = git.execute(command=cmd, with_extended_output=False)
    except GitCommandError:
        raise ValueError(f'"{path}" is not in tracked by this repository.')

    # The date_str is in the following format: Sat Jun 21 10:20:31 2014 -0300
    last_commit_time = datetime.strptime(date_str, "%a %b %d %H:%M:%S %Y %z")
    last_commit_date = last_commit_time.date()

    today_date = local_today()

    time_delta = today_date - last_commit_date

    return time_delta.days
