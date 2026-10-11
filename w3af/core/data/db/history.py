"""
history.py

Copyright 2009 Andres Riancho

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

import os
import threading
from functools import wraps
from shutil import rmtree
from typing import ClassVar

from w3af.core.data.db.dbms import get_default_temp_db_instance
from w3af.core.data.db.history_repository import HistoryRepository
from w3af.core.data.db.history_trace_compressor import (
    HistoryTraceCompressor,
    PendingCompressionJob,
)
from w3af.core.data.db.history_trace_serializer import (
    HistoryTraceSerializer,
    TraceReadException,
)
from w3af.core.data.db.history_trace_storage import HistoryTraceStorage
from w3af.core.filesystem import get_temp_dir

__all__ = ["HistoryItem", "PendingCompressionJob", "TraceReadException"]


def verify_has_db(meth):

    @wraps(meth)
    def inner_verify_has_db(self, *args, **kwds):
        if self._db is None:
            raise RuntimeError("The database is not initialized yet.")
        return meth(self, *args, **kwds)

    return inner_verify_has_db


class HistoryItem:
    """
    Represents history item
    """

    _DATA_TABLE = "history_items"
    _COLUMNS: ClassVar[list[tuple[str, str]]] = [
        ("id", "INTEGER"),
        ("url", "TEXT"),
        ("code", "INTEGER"),
        ("tag", "TEXT"),
        ("mark", "INTEGER"),
        ("info", "TEXT"),
        ("time", "FLOAT"),
        ("msg", "TEXT"),
        ("content_type", "TEXT"),
        ("charset", "TEXT"),
        ("method", "TEXT"),
        ("response_size", "INTEGER"),
        ("codef", "INTEGER"),
        ("alias", "TEXT"),
        ("has_qs", "INTEGER"),
    ]
    _PRIMARY_KEY_COLUMNS = ("id",)
    _INDEX_COLUMNS = ("alias",)

    _EXTENSION = "trace"
    _MSGPACK_CANARY = "cute-and-yellow"

    _TMP_EXTENSION = "tmp"

    _COMPRESSED_EXTENSION = HistoryTraceCompressor._COMPRESSED_EXTENSION
    _COMPRESSED_FILE_BATCH = HistoryTraceCompressor._COMPRESSED_FILE_BATCH
    _UNCOMPRESSED_FILES = HistoryTraceCompressor._UNCOMPRESSED_FILES
    _MIN_FILE_COUNT = HistoryTraceCompressor._MIN_FILE_COUNT

    id = None
    url = None
    _request = None
    _response = None
    info = None
    mark = False
    tag = ""
    content_type = ""
    response_size = 0
    method = "GET"
    msg = "OK"
    code = 200
    time = 0.2
    charset = None

    def __init__(self, db=None):
        self._db = get_default_temp_db_instance() if db is None else db
        self._history_lock = threading.RLock()

        self._session_dir = os.path.join(
            get_temp_dir(), self._db.get_file_name() + "_traces"
        )
        self._history_repository = HistoryRepository(
            self._db,
            self._DATA_TABLE,
            self._COLUMNS,
            self._PRIMARY_KEY_COLUMNS,
            self._INDEX_COLUMNS,
        )
        self._trace_serializer = HistoryTraceSerializer(self._MSGPACK_CANARY)
        self._trace_storage = HistoryTraceStorage(
            self._session_dir, self._trace_serializer
        )
        self._trace_compressor = HistoryTraceCompressor(self._session_dir)

    def get_session_dir(self):
        return self._session_dir

    def init(self):
        self.init_traces_dir()
        self.init_db()

    def init_traces_dir(self):
        with self._history_lock:
            if not os.path.exists(self._session_dir):
                os.mkdir(self._session_dir)

    def init_db(self):
        """
        Init history table and indexes.
        """
        with self._history_lock:
            self._history_repository.init()

    def get_response(self):
        resp = self._response
        if not resp and self.id:
            self._request, resp = self.load_from_file(self.id)
            self._response = resp
        return resp

    def set_response(self, resp):
        self._response = resp

    response = property(get_response, set_response)

    def get_request(self):
        req = self._request
        if not req and self.id:
            req, self._response = self.load_from_file(self.id)
            self._request = req
        return req

    def set_request(self, req):
        self._request = req

    request = property(get_request, set_request)

    @verify_has_db
    def find(self, search_data):
        """
        Find the items matching all the conditions.

        :param search_data: A list of (column, value, operator) tuples, for
                            example [("alias", "abc", "=")]
        :return: A list with the HistoryItem instances that match
        """
        rows = self._history_repository.find(search_data)

        result = []
        for row in rows:
            item = self.__class__(db=self._db)
            item._load_from_row(row)
            result.append(item)
        return result

    def _load_from_row(self, row):
        """
        Load data from row with all columns
        """
        self.id = row[0]
        self.url = row[1]
        self.code = row[2]
        self.tag = row[3]
        self.mark = bool(row[4])
        self.info = row[5]
        self.time = float(row[6])
        self.msg = row[7]
        self.content_type = row[8]
        self.charset = row[9]
        self.method = row[10]
        self.response_size = int(row[11])

    def _get_trace_filename_for_id(self, _id):
        return self._trace_storage.get_trace_filename(_id)

    def _load_from_trace_file(self, _id):
        return self._trace_storage.load_from_trace_file(_id)

    def _load_from_string(self, serialized_req_res):
        return self._trace_storage.load_from_string(serialized_req_res)

    def _load_from_trace_file_concurrent(self, _id):
        return self._trace_storage.load_from_trace_file_concurrent(_id)

    def load_from_file(self, _id):
        return self._trace_storage.load_from_file(_id)

    def _load_from_zip(self, _id):
        return self._trace_storage.load_from_zip(_id)

    def _load_from_zip_file(self, _id, zip_file):
        return self._trace_storage.load_from_zip_file(_id, zip_file)

    @verify_has_db
    def load(self, _id, retry=True):
        """
        Load data from DB by ID
        """
        row = self._history_repository.load(_id, retry)
        self._load_from_row(row)
        return True

    @verify_has_db
    def read(self, _id):
        """
        Return item by ID
        """
        result_item = self.__class__(db=self._db)
        result_item.load(_id)
        return result_item

    def save(self):
        """
        Save History instance to DB and disk
        """
        resp = self.response
        code = int(resp.get_code()) / 100

        values = [
            resp.get_id(),
            self.request.get_uri().url_string,
            resp.get_code(),
            self.tag,
            int(self.mark),
            str(resp.info()),
            resp.get_wait_time(),
            resp.get_msg(),
            resp.content_type,
            resp.charset,
            self.request.get_method(),
            len(resp.body),
            code,
            resp.get_alias(),
            int(self.request.get_uri().has_query_string()),
        ]

        self._history_repository.insert(values)
        self.id = self.response.get_id()

        self._trace_storage.save_trace(self.request, self.response, self.id)

        response_id = resp.get_id()
        self._queue_compression_requests(response_id)

        pending_compression = self._get_pending_compression_job()

        if pending_compression is not None:
            self._process_pending_compression(pending_compression)

        return True

    @staticmethod
    def _raise_if_trace_directory_missing(path_fname):
        HistoryTraceStorage._raise_if_trace_directory_missing(path_fname)

    def _get_pending_compression_job(self):
        return self._trace_compressor.get_pending_job()

    def _queue_compression_requests(self, response_id):
        self._trace_compressor.queue(response_id)

    def _process_pending_compression(
        self, pending_compression: PendingCompressionJob
    ) -> None:
        self._trace_compressor.process(pending_compression)

    def get_columns(self):
        return self._COLUMNS

    def get_table_name(self):
        return self._DATA_TABLE

    def get_primary_key_columns(self):
        return self._PRIMARY_KEY_COLUMNS

    def get_index_columns(self):
        return self._INDEX_COLUMNS

    def clear(self):
        """Clear history and delete all trace files."""
        if self._db is None:
            return

        # Remove the table if it still exists, I verify if it exists
        # before removing it in order to allow clear() to be called more than
        # once in a consecutive way
        self._history_repository.clear()

        self._db = None

        # It might be the case that another thread removes the session dir
        # at the same time as we, so we simply ignore errors here
        rmtree(self._session_dir, ignore_errors=True)

        return True

    def __repr__(self):
        return f"<HistoryItem {self.method} {self.url}>"
