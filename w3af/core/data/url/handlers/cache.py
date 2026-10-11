"""
cache.py

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

import urllib.error
import urllib.parse
import urllib.request

from w3af.core.data.db.dbms import SQLiteDBMS
from w3af.core.data.db.exceptions import DBException
from w3af.core.data.misc.number_generator import NumberGenerator
from w3af.core.data.url.handlers.cache_backend.db import SQLCachedResponse

# TODO: Why not POST? Why don't we perform real caching and respect
# the cache headers/meta tags?
# @see: https://bitbucket.org/jaraco/jaraco.net/src/65af6e442d21/jaraco/net/http/caching.py
CACHE_METHODS = ("GET", "HEAD")


class CacheHandler(urllib.request.BaseHandler):
    """
    Stores responses in a persistent on-disk cache.

    If a subsequent GET request is made for the same URL, the stored
    response is returned, saving time, resources and bandwidth

    :author: Version 0.1 by Staffan Malmgren <staffan@tomtebo.org>
    :author: Version 0.2 by Andres Riancho
    :author: Version 0.3 by Javier Andalia <jandalia =at= gmail.com>
    """

    def __init__(self, id_generator=None, db: SQLiteDBMS | None = None):
        if db is None:
            raise ValueError("CacheHandler requires a database")
        self._id_generator = NumberGenerator() if id_generator is None else id_generator
        self._db = db
        CacheClass.init(db=self._db)

    def clear(self):
        """
        Clear the cache (remove all files and directories associated with it).
        """
        return CacheClass.clear(db=self._db)

    def default_open(self, request):
        """
        :param request: HTTP request
        :return: None if another handler should attempt to answer this request
        """
        method = request.get_method().upper()

        if method not in CACHE_METHODS:
            return None

        if not request.get_from_cache:
            return None

        try:
            cache_response_obj = CacheClass(request, db=self._db)
        except (AttributeError, TypeError, ValueError, DBException):
            # The request might not be in the cache, the cache gets corrupted,
            # or the initial HTTP request that's saved to disk doesn't completely respect the
            # RFC and when we try to read it, it crashes.

            # Send None to the urllib2 framework, which means that we don't
            # know how to handle the request, and we forward it to the next
            # handler in the list.
            return None
        else:
            return cache_response_obj

    def http_response(self, request, response):
        # Set unique numeric identifier
        request.id = response.id = self._id_generator.inc()
        CacheClass.store_in_cache(request, response, db=self._db)
        return response

    https_response = http_response


# This is the default implementation
CacheClass = SQLCachedResponse
