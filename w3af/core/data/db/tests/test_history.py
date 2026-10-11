# -*- coding: UTF-8 -*-
"""
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

import os.path
import secrets
import shutil
import unittest
import zipfile

import msgpack
import pytest

from w3af.core.data.db.dbms import (
    SQLiteDBMS,
    create_temp_db_instance,
    get_default_temp_db_instance,
)
from w3af.core.data.db.exceptions import DBException
from w3af.core.data.db.history import (
    HistoryItem,
    PendingCompressionJob,
    TraceReadException,
)
from w3af.core.data.db.history_trace_compressor import HistoryTraceCompressor
from w3af.core.data.dc.headers import Headers
from w3af.core.data.fuzzer.utils import rand_alnum
from w3af.core.data.kb.knowledge_base import DBKnowledgeBase
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.url.http_request import HTTPRequest
from w3af.core.data.url.http_response import HTTPResponse
from w3af.core.filesystem import create_temp_dir, remove_temp_dir
from w3af.plugins.tests.helper import LOREM


@pytest.mark.smoke
class TestHistoryItem(unittest.TestCase):

    def setUp(self):
        kb.cleanup()
        create_temp_dir()
        HistoryItem(db=get_default_temp_db_instance()).init()

    def tearDown(self):
        remove_temp_dir()
        HistoryItem(db=get_default_temp_db_instance()).clear()
        kb.cleanup()

    def test_single_db(self):
        h1 = HistoryItem(db=get_default_temp_db_instance())
        h2 = HistoryItem(db=get_default_temp_db_instance())
        self.assertEqual(h1._db, h2._db)

    def test_compression_state_is_local_to_each_history_session(self):
        first = HistoryTraceCompressor("first")
        second = HistoryTraceCompressor("second")
        job = PendingCompressionJob(1, 2)

        first._pending_compression_jobs.append(job)

        self.assertEqual(first.get_pending_job(), job)
        self.assertIsNone(second.get_pending_job())
        self.assertEqual(first._latest_compression_job_end, 0)
        self.assertEqual(second._latest_compression_job_end, 0)

    def test_injected_database_is_preserved_by_find(self):
        first_db = create_temp_db_instance()
        second_db = create_temp_db_instance()
        first = HistoryItem(db=first_db)
        second = HistoryItem(db=second_db)
        self.addCleanup(self.close_db, first_db)
        self.addCleanup(self.close_db, second_db)

        first.init()
        second.init()
        first._history_repository.insert(
            [
                1,
                "http://w3af.org/",
                200,
                "",
                0,
                "",
                0.1,
                "OK",
                "text/html",
                "utf-8",
                "GET",
                0,
                2,
                "first",
                0,
            ]
        )

        self.assertIs(first.find([])[0]._db, first_db)
        self.assertIs(first.read(1)._db, first_db)
        self.assertEqual(second.find([]), [])
        self.assertIsNot(first._db, second._db)

    @staticmethod
    def close_db(db: SQLiteDBMS):
        if not db.sql_executor.get_received_poison_pill():
            db.close()

    def test_find(self):
        find_id = secrets.randbelow(499) + 1
        url = URL("http://w3af.org/a/b/foobar.php?foo=123")
        tag_value = rand_alnum(10)

        for i in range(500):
            request = HTTPRequest(url)
            code = 200
            if i == find_id:
                code = 302

            hdr = Headers([("Content-Type", "text/html")])
            res = HTTPResponse(code, "<html>", hdr, url, url, charset="UTF-8")
            h1 = HistoryItem(db=get_default_temp_db_instance())
            h1.request = request
            res.set_id(i)
            h1.response = res

            if i == find_id:
                h1.mark = True
                h1.tag = tag_value
            h1.save()

        h2 = HistoryItem(db=get_default_temp_db_instance())
        self.assertEqual(len(h2.find([("tag", "%" + tag_value + "%", "like")])), 1)
        self.assertEqual(len(h2.find([("code", 302, "=")])), 1)
        self.assertEqual(len(h2.find([("mark", 1, "=")])), 1)
        self.assertEqual(len(h2.find([("has_qs", 1, "=")])), 500)
        self.assertEqual(len(h2.find([])), 500)
        search_data = [("id", find_id + 1, "<"), ("id", find_id - 1, ">")]
        self.assertEqual(len(h2.find(search_data)), 1)

    def test_mark(self):
        mark_id = 3
        url = URL("http://w3af.org/a/b/c.php")

        for i in range(500):
            request = HTTPRequest(url, data="a=1")
            hdr = Headers([("Content-Type", "text/html")])
            res = HTTPResponse(200, "<html>", hdr, url, url, charset="UTF-8")
            h1 = HistoryItem(db=get_default_temp_db_instance())
            h1.request = request
            res.set_id(i)
            h1.response = res
            h1.mark = i == mark_id
            h1.save()

        h2 = HistoryItem(db=get_default_temp_db_instance())
        h2.load(mark_id)
        self.assertTrue(h2.mark)

        h3 = HistoryItem(db=get_default_temp_db_instance())
        h3.load(mark_id - 1)
        self.assertFalse(h3.mark)

    def test_save_load(self):
        i = secrets.randbelow(499) + 1
        url = URL("http://w3af.com/a/b/c.php")
        request = HTTPRequest(url, data="a=1")

        hdr = Headers([("Content-Type", "text/html")])
        res = HTTPResponse(200, "<html>", hdr, url, url, charset="UTF-8")

        h1 = HistoryItem(db=get_default_temp_db_instance())
        h1.request = request
        res.set_id(i)
        h1.response = res
        h1.save()

        h2 = HistoryItem(db=get_default_temp_db_instance())
        h2.load(i)

        self.assertEqual(h1.request.to_dict(), h2.request.to_dict())
        self.assertEqual(h1.response.body, h2.response.body)

    def test_load_not_exists(self):
        h = HistoryItem(db=get_default_temp_db_instance())
        self.assertRaises(DBException, h.load, 1)

    def test_save_load_compressed(self):
        force_compression_count = (
            HistoryItem._UNCOMPRESSED_FILES + HistoryItem._COMPRESSED_FILE_BATCH
        )
        force_compression_count += 150

        url = URL("http://w3af.com/a/b/c.php")
        headers = Headers([("Content-Type", "text/html")])
        body = "<html>" + LOREM * 20

        for i in range(1, force_compression_count):
            request = HTTPRequest(url, data=f"a={i}")

            response = HTTPResponse(200, body, headers, url, url, charset="UTF-8")
            response.set_id(i)

            h = HistoryItem(db=get_default_temp_db_instance())
            h.request = request
            h.response = response
            h.save()

        compressed_file = os.path.join(h.get_session_dir(), "1-150.zip")
        self.assertTrue(os.path.exists(compressed_file))

        compressed_file_temp = os.path.join(h.get_session_dir(), "1-150.zip.tmp")
        self.assertFalse(os.path.exists(compressed_file_temp))

        expected_files = [
            f"{i}.trace" for i in range(1, HistoryItem._COMPRESSED_FILE_BATCH + 1)
        ]

        _zip = zipfile.ZipFile(compressed_file, mode="r")
        self.assertEqual(_zip.namelist(), expected_files)

        for i in range(1, 100):
            h = HistoryItem(db=get_default_temp_db_instance())
            h.load(i)

            self.assertEqual(h.request.get_uri(), url)
            self.assertEqual(h.response.get_headers(), headers)
            self.assertEqual(h.response.get_body(), body)

    def test_clear(self):
        url = URL("http://w3af.com/a/b/c.php")
        request = HTTPRequest(url, data="a=1")
        hdr = Headers([("Content-Type", "text/html")])
        res = HTTPResponse(200, "<html>", hdr, url, url, charset="UTF-8")

        h1 = HistoryItem(db=get_default_temp_db_instance())
        h1.request = request
        res.set_id(1)
        h1.response = res
        h1.save()

        table_name = h1.get_table_name()
        db = get_default_temp_db_instance()

        self.assertTrue(db.table_exists(table_name))

        clear_result = h1.clear()

        self.assertTrue(clear_result)
        self.assertFalse(os.path.exists(h1._session_dir), f"{h1._session_dir} exists.")

        # Changed the meaning of clear a little bit... now it simply removes
        # all rows from the table, not the table itself
        self.assertTrue(db.table_exists(table_name))

    def test_clear_clear(self):
        url = URL("http://w3af.com/a/b/c.php")
        request = HTTPRequest(url, data="a=1")
        hdr = Headers([("Content-Type", "text/html")])
        res = HTTPResponse(200, "<html>", hdr, url, url, charset="UTF-8")

        h1 = HistoryItem(db=get_default_temp_db_instance())
        h1.request = request
        res.set_id(1)
        h1.response = res
        h1.save()

        h1.clear()
        h1.clear()

    def test_init_init(self):
        # No exceptions should be raised
        HistoryItem(db=get_default_temp_db_instance()).init()
        HistoryItem(db=get_default_temp_db_instance()).init()

    def test_tag(self):
        tag_id = secrets.randbelow(499) + 501
        tag_value = rand_alnum(10)
        url = URL("http://w3af.org/a/b/c.php")

        for i in range(501, 1000):
            request = HTTPRequest(url, data="a=1")
            hdr = Headers([("Content-Type", "text/html")])
            res = HTTPResponse(200, "<html>", hdr, url, url, charset="UTF-8")
            h1 = HistoryItem(db=get_default_temp_db_instance())
            h1.request = request
            res.set_id(i)
            h1.response = res
            if i == tag_id:
                h1.tag = tag_value
            h1.save()

        h2 = HistoryItem(db=get_default_temp_db_instance())
        h2.load(tag_id)
        self.assertEqual(h2.tag, tag_value)

    def test_save_load_unicode_decode_error(self):
        url = URL("http://w3af.com/a/b/é.php?x=á")
        request = HTTPRequest(url, data="a=1")
        headers = Headers([("Content-Type", "text/html")])

        res = HTTPResponse(200, "<html>", headers, url, url, charset="UTF-8")
        res.set_id(1)

        h1 = HistoryItem(db=get_default_temp_db_instance())
        h1.request = request
        h1.response = res
        h1.save()

        h2 = HistoryItem(db=get_default_temp_db_instance())
        h2.load(1)

        self.assertEqual(h1.request.to_dict(), h2.request.to_dict())
        self.assertEqual(h1.response.body, h2.response.body)
        self.assertEqual(h1.request.url_object, h2.request.url_object)

    def save_item(self, _id, url="http://w3af.com/a/b/c.php"):
        url = URL(url)
        hdr = Headers([("Content-Type", "text/html")])
        res = HTTPResponse(200, "<html>", hdr, url, url, charset="UTF-8")
        res.set_id(_id)

        item = HistoryItem(db=get_default_temp_db_instance())
        item.request = HTTPRequest(url, data="a=1")
        item.response = res
        item.save()
        return item

    def test_read(self):
        self.save_item(7)

        item = HistoryItem(db=get_default_temp_db_instance()).read(7)

        self.assertEqual(item.id, 7)
        self.assertEqual(item.url, "http://w3af.com/a/b/c.php")
        self.assertEqual(repr(item), "<HistoryItem POST http://w3af.com/a/b/c.php>")

    def test_found_items_load_traffic_lazily(self):
        self.save_item(8, url="http://w3af.com/lazy.php")

        (response_first,) = HistoryItem(db=get_default_temp_db_instance()).find(
            [("id", 8, "=")]
        )
        (request_first,) = HistoryItem(db=get_default_temp_db_instance()).find(
            [("id", 8, "=")]
        )

        self.assertEqual(response_first.response.get_body(), "<html>")
        self.assertEqual(
            response_first.request.get_uri().url_string, "http://w3af.com/lazy.php"
        )
        self.assertEqual(request_first.request.get_method(), "POST")
        self.assertEqual(request_first.response.get_code(), 200)

    def test_invalid_search(self):
        self.assertRaises(
            DBException,
            HistoryItem(db=get_default_temp_db_instance()).find,
            [("id", 1, "nonsense")],
        )

    def test_load_without_table(self):
        h = HistoryItem(db=get_default_temp_db_instance())
        h._require_db().drop_table(h.get_table_name()).result()

        self.assertRaises(DBException, h.load, 1)

    def test_methods_require_a_database(self):
        h = HistoryItem(db=get_default_temp_db_instance())
        h.clear()

        self.assertRaises(RuntimeError, h.find, [])
        self.assertRaises(RuntimeError, h.load, 1)
        self.assertRaises(RuntimeError, h.read, 1)

    def test_load_from_string_errors(self):
        h = HistoryItem(db=get_default_temp_db_instance())

        self.assertRaises(TraceReadException, h._load_from_string, b"\x01\x02")
        self.assertRaises(TraceReadException, h._load_from_string, msgpack.dumps(None))
        self.assertRaises(
            TraceReadException,
            h._load_from_string,
            msgpack.dumps(({}, {}, "wrong-canary")),
        )
        self.assertRaises(TraceReadException, h._load_from_trace_file, 404)

    def test_load_from_file_without_trace_nor_zip(self):
        self.assertRaises(
            TraceReadException,
            HistoryItem(db=get_default_temp_db_instance()).load_from_file,
            404,
        )

    def test_load_from_corrupt_trace_file_times_out(self):
        h = HistoryItem(db=get_default_temp_db_instance())
        with open(h._get_trace_filename_for_id(9), "wb") as trace_file:
            trace_file.write(msgpack.dumps(None))

        self.assertRaises(DBException, h.load_from_file, 9)

    def test_load_from_invalid_zip_file(self):
        h = HistoryItem(db=get_default_temp_db_instance())
        with open(os.path.join(h.get_session_dir(), "1-150.zip"), "wb") as zip_file:
            zip_file.write(b"not a zip file")

        self.assertRaises(TraceReadException, h._load_from_zip, 3)
        self.assertRaises(TraceReadException, h.load_from_file, 3)

    def test_load_from_zip_without_the_trace(self):
        h = HistoryItem(db=get_default_temp_db_instance())
        zip_path = os.path.join(h.get_session_dir(), "1-150.zip")
        with zipfile.ZipFile(zip_path, mode="w") as zip_file:
            zip_file.writestr("1.trace", b"")

        self.assertRaises(TraceReadException, h._load_from_zip, 3)

    def test_compress_missing_trace_files(self):
        h = self.save_item(1)
        session_dir = h.get_session_dir()

        h._process_pending_compression(PendingCompressionJob(1, 3))

        self.assertFalse(os.path.exists(os.path.join(session_dir, "1.trace")))
        with zipfile.ZipFile(os.path.join(session_dir, "1-3.zip")) as zip_file:
            self.assertEqual(zip_file.namelist(), ["1.trace"])

        self.assertEqual(
            HistoryItem(db=get_default_temp_db_instance()).read(1).response.get_body(),
            "<html>",
        )

    def test_save_without_traces_directory(self):
        h = HistoryItem(db=get_default_temp_db_instance())
        session_dir = h.get_session_dir()
        shutil.rmtree(session_dir)

        with self.assertRaises(OSError) as context:
            self.save_item(10)

        self.assertIn(
            f'Directory does not exist: "{session_dir}"', str(context.exception)
        )

    def test_save_fails_with_existing_directories(self):
        h = HistoryItem(db=get_default_temp_db_instance())
        os.mkdir(h._get_trace_filename_for_id(11))

        self.assertRaises(IsADirectoryError, self.save_item, 11)


kb = DBKnowledgeBase()
