"""
dns_cache.py

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

import socket
from functools import partial

from w3af.core.data.misc.lru import SynchronizedLRUDict

_resolve = socket.getaddrinfo
_dns_cache = SynchronizedLRUDict(200)


def _caching_getaddrinfo(output, *args, **kwargs):
    query = (args, frozenset(kwargs.items()))

    try:
        return _dns_cache[query]
    except KeyError:
        res = _resolve(*args, **kwargs)
        _dns_cache[query] = res
        output.debug(f"DNS response from DNS server for domain: {args[0]}")
        return res


def enable_dns_cache(output):
    """
    DNS cache trick

    This will speed up all the test! Before this dns cache voodoo magic every
    request to the HTTP server required a DNS query, this is slow on some
    networks so I added this feature.

    This method was taken from:
    # $Id: download.py,v 1.30 2004/05/13 09:55:30 torh Exp $
    That is part of :
    swup-0.0.20040519/

    Developed by:
    #  Copyright 2001 - 2003 Trustix AS - <http://www.trustix.com>
    #  Copyright 2003 - 2004 Tor Hveem - <tor@bash.no>
    #  Copyright 2004 Omar Kilani for tinysofa - <http://www.tinysofa.org>
    """
    global _resolve

    if getattr(socket.getaddrinfo, "func", None) is not _caching_getaddrinfo:
        _resolve = socket.getaddrinfo

    output.debug("Enabling _dns_cache()")
    socket.getaddrinfo = partial(_caching_getaddrinfo, output)
    return disable_dns_cache


def disable_dns_cache():
    """Restore the resolver and release cached DNS responses."""
    if getattr(socket.getaddrinfo, "func", None) is _caching_getaddrinfo:
        socket.getaddrinfo = _resolve
    _dns_cache.clear()
