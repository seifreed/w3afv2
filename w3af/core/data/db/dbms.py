"""
dbms.py

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
import os
import sqlite3
from concurrent.futures import Future
from functools import wraps
from multiprocessing.dummy import Process, Queue
from uuid import uuid4

from w3af.core.data.db.exceptions import (
    DBException,
    MalformedDBException,
    NoSuchTableException,
)
from w3af.core.data.db.sql_identifier import require_safe_identifier
from w3af.core.data.misc.file_utils import replace_file_special_chars
from w3af.core.filesystem import create_temp_dir, get_temp_dir

LOGGER = logging.getLogger(__name__)

# Constants
SETUP = "SETUP"
QUERY = "QUERY"
SELECT = "SELECT"
COMMIT = "COMMIT"
POISON = "POISON"

JOURNAL_MODE = "OFF"
CACHE_SIZE = 2000
SELECT_BATCH_SIZE = 100

DB_MALFORMED_ERROR = (
    "SQLite raised a database disk image is malformed"
    " exception. While we do have good understanding on the"
    " many reasons that"
    " might lead to this issue [0] and multiple bug reports"
    " by users [1] there is no clear indication on exactly"
    " what causes the issue in w3af.\n\n"
    ""
    "If you are able to reproduce this issue in your"
    " environment we would love to hear the OS and hardware"
    " details, steps to reproduce, and any other related"
    " information. Just send us a comment at #4905 [1].\n\n"
    ""
    "[0] https://www.sqlite.org/howtocorrupt.html\n"
    "[1] https://github.com/andresriancho/w3af/issues/4905"
)


def verify_started(meth):

    @wraps(meth)
    def inner_verify_started(self, *args, **kwds):
        msg = "No calls to SQLiteDBMS can be made after stop()."

        # The executor thread only finishes after receiving the poison pill
        if self.sql_executor.get_received_poison_pill():
            raise RuntimeError(msg)

        return meth(self, *args, **kwds)

    return inner_verify_started


class SQLiteDBMS:
    """
    Wrap sqlite connection in a way that allows concurrent requests from
    multiple threads.

    This is done by internally queuing the requests and processing them
    sequentially in a separate thread (in the same order they arrived).

    For all requests performed by the client, a Future [0] is returned, in
    other words, this is an asynchronous class.

    [0] http://www.python.org/dev/peps/pep-3148/
    """

    def __init__(self, filename):

        super().__init__()

        #
        #   All DB queries from w3af are sent to this queue, and this is a lot
        #   since the DiskList, DiskQueue, DiskDict classes which are used
        #   extensively through the framework use the same SQLite db as a
        #   backend (of course different tables, but the same SQLite file and
        #   on-memory instance).
        #
        #   Limiting the size of this Queue is serious business. I can't think
        #   about a scenario where this limit would create a thread-lock, but
        #   it doesn't feel right...
        #
        #   I've added debugging to the SQLiteExecutor.run() method to
        #   analyze when the queue is full. After just a couple of minutes of
        #   running the following message is shown:
        #
        #   The SQLiteExecutor.in_queue length is 0. Processed 14500 queries.
        #
        #   The queue size is 0, and other messages keep showing that same
        #   number, or other <10, and the processed queries is really high but
        #   acceptable: SQLite is C, fast, etc.
        #
        #   Any dead-lock you might be looking for doesn't seem to be here.
        #
        in_queue = Queue(250)
        self.sql_executor = SQLiteExecutor(in_queue)
        self.sql_executor.start()

        #
        #    Performs sqlite database setup, this has the nice side-effect
        #    that .result() will block until the thread is started and
        #    processing tasks.
        #
        future = self.sql_executor.setup(filename)

        try:
            future.result()
        except DBException:
            # Do not leave the executor thread behind when setup fails
            self.sql_executor.stop().result()
            raise

        self.filename = filename

    @verify_started
    def execute(self, query, parameters=(), commit=False):
        """
        `execute` calls are non-blocking: just queue up the request and
        return a future.
        """
        fr = self.sql_executor.query(query, parameters)

        if commit:
            self.commit()

        return fr

    @verify_started
    def select(self, query, parameters=()):
        """
        I can't think about any non-blocking use of calling select()
        """
        future = self.sql_executor.select(query, parameters)
        return future.result()

    def select_in_batches(self, query, parameters=(), batch_size=SELECT_BATCH_SIZE):
        """Yield SELECT rows in bounded batches instead of one large list."""
        if batch_size <= 0:
            raise ValueError("batch_size must be greater than zero")

        offset = 0
        while True:
            batch_query = f"{query} LIMIT ? OFFSET ?"
            batch_parameters = (*parameters, batch_size, offset)
            rows = self.select(batch_query, batch_parameters)

            yield from rows

            if len(rows) < batch_size:
                return

            offset += batch_size

    @verify_started
    def select_one(self, query, parameters=()):
        """
        :return: Only the first row of the SELECT, or None if there are no
        matching rows.
        """
        try:
            return self.select(query, parameters)[0]
        except IndexError:
            return None

    @verify_started
    def commit(self):
        # Send the task and wait for the execution
        future = self.sql_executor.commit()
        future.result()

    @verify_started
    def close(self):
        # Commit all pending changes
        self.commit()

        # Setting the received poison pill to True will make all calls to
        # SQLiteDBMS methods fail because of `@verify_started`. The goal is
        # to prevent other tasks being queued after the poison pill
        self.sql_executor.set_received_poison_pill(True)

        # And then send the poison pill and wait for it to be processed by
        # the run() method
        future = self.sql_executor.stop()
        future.result()

    def get_file_name(self):
        """Return DB filename."""
        return self.filename

    def drop_table(self, name):
        query = f"DROP TABLE {require_safe_identifier(name)}"
        return self.execute(query, commit=True)

    def clear_table(self, name):
        """
        Remove all rows from a table.
        """
        query = "DELETE FROM %s WHERE 1=1"
        return self.execute(query % require_safe_identifier(name), commit=True)

    def create_table(self, name, columns, pk_columns=()):
        """
        Create table in convenient way.
        """
        query = f"CREATE TABLE {require_safe_identifier(name)} ("

        all_columns = []
        for column_data in columns:
            column_name, column_type = column_data
            all_columns.append(f"{column_name} {column_type}")

        query += ", ".join(all_columns)

        if pk_columns:
            query += ", PRIMARY KEY ({})".format(",".join(pk_columns))

        query += ")"

        return self.execute(query, commit=True)

    def table_exists(self, name):
        query = (
            "SELECT name FROM sqlite_master WHERE type='table'" " AND name=? LIMIT 1"
        )
        r = self.select(query, (name,))
        return bool(r)

    def create_index(self, table, columns):
        """
        Create index for speed and performance

        :param table: The table from which you want to create an index from
        :param columns: A list of column names.
        """
        table = require_safe_identifier(table)
        safe_columns = ",".join(require_safe_identifier(c) for c in columns)
        query = f"CREATE INDEX {table}_index ON {table}( {safe_columns} )"

        return self.execute(query, commit=True)


class SQLiteExecutor(Process):
    """
    A very simple thread that takes work via submit() and processes it in a
    different thread.
    """

    def __init__(self, in_queue):
        super().__init__(name="SQLiteExecutor")

        # Setting the thread to daemon mode so it dies with the rest of the
        # process, and a name so we can identify it during debugging sessions
        self.daemon = True
        self.name = "SQLiteExecutor"

        self._in_queue = in_queue
        self._current_query_num = 0
        self.conn = None
        self._poison_pill_received = False

    def get_received_poison_pill(self):
        return self._poison_pill_received

    def set_received_poison_pill(self, received):
        self._poison_pill_received = received

    def _report_qsize_limit_reached(self):
        """
        Report if the queue size has reached the limit.

        When the limit is hit, all the different framework components, such as
        DiskDict, DiskList, KB, etc. will start to lock waiting for the DB result,
        which considerably degrades performance.

        :return: None
        """
        if self._in_queue.qsize() >= self._in_queue.maxsize - 10:
            msg = (
                "The SQLiteExecutor.in_queue length has reached its max"
                " limit of %s after processing %s queries. Framework"
                " performance will degrade."
            )
            args = (self._in_queue.maxsize, self._current_query_num)
            LOGGER.debug(msg % args)

    def query(self, query, parameters):
        future = Future()
        request = (QUERY, (query, parameters), {}, future)
        self._in_queue.put(request)
        return future

    def _query_handler(self, query, parameters):
        cursor = self.conn.cursor()
        return cursor.execute(query, parameters)

    def select(self, query, parameters):
        future = Future()
        request = (SELECT, (query, parameters), {}, future)
        self._in_queue.put(request)
        return future

    def _select_handler(self, query, parameters):
        return list(self.cursor.execute(query, parameters))

    def commit(self):
        future = Future()
        request = (COMMIT, None, None, future)
        self._in_queue.put(request)
        return future

    def _commit_handler(self):
        return self.conn.commit()

    def stop(self):
        future = Future()
        request = (POISON, None, None, future)
        self._in_queue.put(request)
        return future

    def setup(self, filename):
        """
        Request the process to perform a setup.
        """
        future = Future()
        request = (SETUP, (filename,), {}, future)
        self._in_queue.put(request)
        return future

    def _setup_handler(self, filename):
        # Convert the filename to UTF-8, this is needed for windows, and special
        # characters, see:
        # http://www.sqlite.org/c3ref/open.html
        self.filename = replace_file_special_chars(filename)

        conn = sqlite3.connect(self.filename, check_same_thread=True)

        try:
            conn.execute(f"PRAGMA journal_mode = {JOURNAL_MODE}")
            conn.execute(f"PRAGMA cache_size = {CACHE_SIZE}")
        except sqlite3.DatabaseError:
            conn.close()
            raise

        conn.text_factory = str
        self.conn = conn

        self.cursor = conn.cursor()

        # Commented line to be: Slower but (hopefully) without malformed
        # databases
        #
        # https://github.com/andresriancho/w3af/issues/4937
        #
        # It doesn't seem to help because I'm still getting malformed database
        # files, but I'll keep it anyways because I'm assuming that it's going
        # to reduce (not to zero, but reduce) these issues.
        #
        # self.cursor.execute('PRAGMA synchronous=OFF')

    def run(self):
        """
        This is the "main" method for this class, the one that
        consumes the commands which are sent to the Queue. The idea is to have
        the following architecture features:
            * Other parts of the framework which want to insert into the DB
              simply add an item to our input Queue and "forget about it" since
              it will be processed in another thread.

            * Only one thread accesses the sqlite3 object, which avoids many
            issues because of sqlite's non thread-safeness

        The Queue.get() will make sure we don't have 100% CPU usage in the loop
        """
        OP_CODES = {
            SETUP: self._setup_handler,
            QUERY: self._query_handler,
            SELECT: self._select_handler,
            COMMIT: self._commit_handler,
            POISON: POISON,
        }

        while True:
            op_code, args, kwds, future = self._in_queue.get()

            self._current_query_num += 1

            args = args or ()
            kwds = kwds or {}

            self._report_qsize_limit_reached()

            if not future.set_running_or_notify_cancel():
                # The client cancelled this request, keep serving the others
                continue

            handler = OP_CODES[op_code]

            if handler == POISON:
                self._poison_pill_received = True
                if self.conn is not None:
                    self.conn.close()
                future.set_result(True)
                break

            try:
                result = handler(*args, **kwds)
            except sqlite3.DatabaseError as e:
                # I don't like this string match, but it seems that the
                # exception doesn't have any error code to match
                if "no such table" in str(e):
                    dbe = NoSuchTableException(str(e))

                elif "malformed" in str(e):
                    print(DB_MALFORMED_ERROR)
                    dbe = MalformedDBException(DB_MALFORMED_ERROR)

                else:
                    # More specific exceptions to be added here later...
                    dbe = DBException(str(e))

                future.set_exception(dbe)

            except Exception as e:
                LOGGER.debug("Unhandled exception in DB worker thread", exc_info=True)
                dbe = DBException(str(e))
                future.set_exception(dbe)

            else:
                future.set_result(result)


temp_default_db = None


def create_temp_db_instance():
    """Create an independently owned temporary database instance."""
    create_temp_dir()
    filename = os.path.join(get_temp_dir(), f"db-{uuid4().hex}.db")
    return SQLiteDBMS(filename)


def get_default_temp_db_instance():
    global temp_default_db

    if temp_default_db is None:
        temp_default_db = create_temp_db_instance()

    return temp_default_db


def get_default_persistent_db_instance():
    """
    At some point I'll want to have persistent DB for storing the KB and other
    information across different w3af processes, or simply to save the findings
    in a KB and don't remove them. I'm adding this method as a reminder of
    where it should be done.
    """
    return get_default_temp_db_instance()
