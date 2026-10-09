"""
__init__.py

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

import logging


#
# Silence noisy scapy IPv6 routing messages
#
class FilterScapy(logging.Filter):
    """A simple way to prevent messages from getting through."""

    def __init__(self, name=None):
        pass

    def filter(self, rec):
        return "No route found for IPv6" not in rec.msg


logger = logging.getLogger("scapy.runtime")
logger.addFilter(FilterScapy())
