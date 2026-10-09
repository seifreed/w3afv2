# -*- coding: UTF-8 -*-
"""
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

import os
import shutil
import sqlite3
import string
import tempfile
import threading
import unittest
from concurrent.futures import Future
from itertools import repeat, starmap
from multiprocessing.dummy import Queue
from random import choice

from w3af.core.data.db.dbms import (
    DB_MALFORMED_ERROR,
    SELECT,
    SQLiteDBMS,
    SQLiteExecutor,
    get_default_persistent_db_instance,
    get_default_temp_db_instance,
)
from w3af.core.data.db.exceptions import (
    DBException,
    MalformedDBException,
    NoSuchTableException,
)


class TestDBMS(unittest.TestCase):
    """
    Each test uses its own directory: removing the shared w3af temp directory
    would also remove the default database other tests are using.
    """

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.temp_dir)

    def new_db(self):
        db = SQLiteDBMS(self.get_temp_filename())
        self.addCleanup(self.close_db, db)
        return db

    @staticmethod
    def close_db(db):
        if not db.sql_executor.get_received_poison_pill():
            db.close()

    def get_temp_filename(self):
        fname = "".join(starmap(choice, repeat((string.ascii_letters,), 18)))
        return os.path.join(self.temp_dir, fname + ".w3af.temp_db")

    def test_open_error(self):
        invalid_filename = "/"
        self.assertRaises(DBException, SQLiteDBMS, invalid_filename)

    def test_simple_db(self):
        db = self.new_db()
        db.create_table("TEST", [("id", "INT"), ("data", "TEXT")]).result()

        db.execute('INSERT INTO TEST VALUES (1,"a")').result()

        self.assertIn((1, "a"), db.select("SELECT * from TEST"))
        self.assertEqual((1, "a"), db.select_one("SELECT * from TEST"))

    def test_update_update_rowcount(self):
        db = self.new_db()
        db.create_table("TEST", [("id", "INT"), ("data", "TEXT")]).result()

        db.execute('INSERT INTO TEST VALUES (1, "a")').result()

        result = db.execute("UPDATE TEST SET data = ? WHERE id = ?", ("b", 1)).result()
        self.assertEqual(result.rowcount, 1)

        # There was a bug here where the same cursor instance was used as a result
        # for two (or more) UPDATE calls, which will override the rowcount value
        #
        # This lead to race conditions like:
        #
        #   https://github.com/andresriancho/w3af/issues/16171
        #
        result1 = db.execute("UPDATE TEST SET data = ? WHERE id = ?", ("c", 1)).result()
        result2 = db.execute(
            "UPDATE TEST SET data = ? WHERE id = ?", ("nope", 3)
        ).result()
        self.assertEqual(result1.rowcount, 1)
        self.assertEqual(result2.rowcount, 0)

    def test_select_non_exist_table(self):
        db = self.new_db()

        self.assertRaises(NoSuchTableException, db.select, "SELECT * from TEST")

    def test_default_db(self):
        db = get_default_temp_db_instance()
        db.create_table("TEST", [("id", "INT"), ("data", "TEXT")]).result()

        db.execute('INSERT INTO TEST VALUES (1,"a")').result()

        self.assertIn((1, "a"), db.select("SELECT * from TEST"))
        self.assertEqual((1, "a"), db.select_one("SELECT * from TEST"))

    def test_simple_db_with_pk(self):
        db = self.new_db()
        fr = db.create_table("TEST", [("id", "INT"), ("data", "TEXT")], ["id"])
        fr.result()

        self.assertEqual([], db.select("SELECT * from TEST"))

    def test_drop_table(self):
        db = self.new_db()
        fr = db.create_table("TEST", [("id", "INT"), ("data", "TEXT")], ["id"])
        fr.result()

        db.drop_table("TEST").result()
        self.assertRaises(DBException, db.drop_table("TEST").result)

    def test_simple_db_with_index(self):
        db = self.new_db()
        fr = db.create_table("TEST", [("id", "INT"), ("data", "TEXT")], ["id"])
        fr.result()

        db.create_index("TEST", ["data"]).result()
        self.assertRaises(DBException, db.create_index("TEST", ["data"]).result)

    def test_table_exists(self):
        db = self.new_db()
        self.assertFalse(db.table_exists("TEST"))

        db = self.new_db()
        db.create_table("TEST", [("id", "INT"), ("data", "TEXT")], ["id"])

        self.assertTrue(db.table_exists("TEST"))

    def test_close_twice(self):
        db = self.new_db()
        db.close()

        self.assertRaises(AssertionError, db.close)

    def test_clear_table_and_select_one_without_rows(self):
        db = self.new_db()
        db.create_table("TEST", [("id", "INT")]).result()
        db.execute("INSERT INTO TEST VALUES (1)").result()

        db.clear_table("TEST").result()

        self.assertIsNone(db.select_one("SELECT * FROM TEST"))

    def test_invalid_filename(self):
        threads = threading.active_count()

        self.assertRaises(DBException, SQLiteDBMS, "embedded\x00null")

        self.assertEqual(threading.active_count(), threads)

    def test_malformed_database(self):
        filename = self.get_temp_filename()

        conn = sqlite3.connect(filename)
        conn.execute("CREATE TABLE TEST (data TEXT)")
        conn.executemany("INSERT INTO TEST VALUES (?)", [("x" * 500,)] * 200)
        conn.commit()
        conn.close()

        # Keep the header and the schema page, corrupt every data page
        with open(filename, "r+b") as db_file:
            data = bytearray(db_file.read())
            data[2048:] = b"\xff" * (len(data) - 2048)
            db_file.seek(0)
            db_file.write(data)

        with self.assertRaises(MalformedDBException) as context:
            SQLiteDBMS(filename)

        self.assertEqual(str(context.exception), DB_MALFORMED_ERROR)

    def test_cancelled_request_is_skipped(self):
        db = self.new_db()

        cancelled = Future()
        cancelled.cancel()
        db.sql_executor._in_queue.put((SELECT, ("SELECT 1", ()), {}, cancelled))

        self.assertEqual(db.select("SELECT 2"), [(2,)])
        self.assertTrue(cancelled.cancelled())

    def test_report_qsize_limit_reached(self):
        in_queue = Queue(11)
        in_queue.put(None)
        executor = SQLiteExecutor(in_queue)

        with self.assertLogs("w3af.core.data.db.dbms", level="DEBUG") as logs:
            executor._report_qsize_limit_reached()

        self.assertIn("has reached its max limit of 11", logs.output[0])

        in_queue.get()
        with self.assertNoLogs("w3af.core.data.db.dbms", level="DEBUG"):
            executor._report_qsize_limit_reached()


class TestDefaultDB(unittest.TestCase):
    def test_get_default_temp_db_instance(self):
        self.assertEqual(
            id(get_default_temp_db_instance()), id(get_default_temp_db_instance())
        )

    def test_get_default_persistent_db_instance(self):
        self.assertIs(
            get_default_persistent_db_instance(), get_default_temp_db_instance()
        )
