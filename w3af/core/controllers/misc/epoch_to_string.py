"""
epoch_to_string.py

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

import datetime
import time


def epoch_to_string(start_time):
    """
    :return: A string that represents in weeks/days/hours/minutes/seconds
             how much time the scan lasted.

    >>> import time
    >>> now = time.time()

    >>> epoch_to_string(now - 1)
    '1 second'

    >>> epoch_to_string(now - 60)
    '1 minute'

    >>> epoch_to_string(now - 61)
    '1 minute 1 second'

    """
    time_delta = datetime.timedelta(seconds=time.time() - start_time)

    weeks, days = divmod(time_delta.days, 7)
    minutes, seconds = divmod(time_delta.seconds, 60)
    hours, minutes = divmod(minutes, 60)

    units = (
        (weeks, "week"),
        (days, "day"),
        (hours, "hour"),
        (minutes, "minute"),
        (seconds, "second"),
    )
    parts = [
        f"{amount} {unit}{'s' if amount > 1 else ''}"
        for amount, unit in units
        if amount
    ]

    return " ".join(parts) or "0 seconds"
