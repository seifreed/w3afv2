"""
cvss.py

Copyright 2017 Andres Riancho

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

from w3af.core.data.constants import severity


def cvss_to_severity(cvss_score):
    """
    Convert CVSS score (1-10) to a w3af severity.

    :param cvss_score: CVSS score (1 to 10)
    :return: A severity
    """
    if cvss_score >= 7:
        return severity.HIGH

    if cvss_score >= 3:
        return severity.MEDIUM

    if cvss_score >= 2:
        return severity.LOW

    return severity.INFORMATION
