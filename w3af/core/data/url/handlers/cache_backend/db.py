"""
db.py

Copyright 2013 Andres Riancho

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

from w3af.core.data.db.dbms import SQLiteDBMS
from w3af.core.data.db.exceptions import DBException
from w3af.core.data.db.history import HistoryItem
from w3af.core.data.url.exceptions import CacheStoreException
from w3af.core.data.url.handlers.cache_backend.cached_response import CachedResponse
from w3af.core.data.url.handlers.cache_backend.utils import gen_hash
from w3af.core.data.url.http_response import HTTPResponse
from w3af.core.exceptions import ScanMustStopException
from w3af.core.filesystem import create_temp_dir

LOGGER = logging.getLogger(__name__)


def store_error(error, request, response):
    """
    :return: The exception to raise when saving a request/response to the
             cache failed: running out of disk stops the scan, anything else
             is reported as a CacheStoreException
    """
    if "disk" in str(error).lower():
        msg = f'A database error was raised: "{error}". Please check if your disk is full.'
        return ScanMustStopException(msg)

    args = (error, response.get_id(), request.get_uri(), response.get_code())
    msg = (
        "Exception while inserting request/response to the"
        ' database: "%s". The request/response that generated'
        " the error is: %s %s %s"
    )
    LOGGER.error(msg, *args)
    return CacheStoreException(msg % args)


class SQLCachedResponse(CachedResponse):

    def __init__(self, req, db: SQLiteDBMS):
        self._hist_obj = None
        self._db = db
        CachedResponse.__init__(self, req)

    def _get_from_response(self, part):

        hist = self._get_hist_obj()

        if part == CachedResponse.PART_HEADER:
            res = hist.info
        elif part == CachedResponse.PART_BODY:
            res = hist.response.body
        elif part == CachedResponse.PART_CODE:
            res = hist.code
        elif part == CachedResponse.PART_MSG:
            res = hist.msg
        elif part == CachedResponse.PART_CHARSET:
            res = hist.charset
        elif part == CachedResponse.PART_TIME:
            res = hist.time
        else:
            raise ValueError(f"Unexpected value for param 'part': {part}")

        return res

    def _get_hist_obj(self):
        hist_obj = self._hist_obj
        if hist_obj is None:
            historyobjs = HistoryItem(db=self._db).find([("alias", self._hash_id, "=")])
            self._hist_obj = hist_obj = historyobjs[0] if historyobjs else None
        return hist_obj

    @staticmethod
    def store_in_cache(request, response, db: SQLiteDBMS | None = None):
        if db is None:
            raise ValueError("SQLCachedResponse requires a database")
        # Create the http response object
        resp = HTTPResponse.from_httplib_resp(response, original_url=request.url_object)
        resp.set_id(response.id)
        resp.set_alias(gen_hash(request))

        hi = HistoryItem(db=db)
        hi.request = request
        hi.response = resp

        # Now save them. The DBMS reports every sqlite error as a DBException
        try:
            hi.save()
        except (DBException, OSError, TypeError, ValueError, AttributeError) as ex:
            raise store_error(ex, request, resp) from ex

    @staticmethod
    def init(db: SQLiteDBMS | None = None):
        if db is None:
            raise ValueError("SQLCachedResponse requires a database")
        create_temp_dir()
        HistoryItem(db=db).init()

    @staticmethod
    def clear(db: SQLiteDBMS):
        """
        Clear the cache (remove all files and directories associated with it).
        """
        return HistoryItem(db=db).clear()
