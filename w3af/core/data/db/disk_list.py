"""
DiskList.py

Copyright 2008 Andres Riancho

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

# magic
import builtins
import hashlib
import heapq
import os
import tempfile
from contextlib import ExitStack

from w3af.core.data.db.dbms import SQLiteDBMS
from w3af.core.data.db.disk_item import DiskItem
from w3af.core.data.fuzzer.utils import rand_alpha
from w3af.core.data.misc.cpickle_dumps import cpickle_dumps
from w3af.core.data.misc.serialize import dump as serialize_dump
from w3af.core.data.misc.serialize import load as serialize_load
from w3af.core.data.misc.serialize import loads

# Disk list states
OPEN = 1
CLOSED = 2


class DiskList:
    """
    A DiskList is a sqlite3 wrapper which has the following features:
        - Implements a list-like API
        - Stores all list items in a sqlite3 table
        - Is thread safe
        - Implements an iterator and a reversed iterator

    I had to replace the old DiskList because the old one did not support
    iteration, and the only way of adding iteration to that object was doing
    something like this:

    def __iter__(self):
        return self._shelve.keys()

    Which in most cases would be stupid, because it would have to retrieve all
    the values saved on disk to memory, and then perform iteration over that
    list. Another problem is that this iteration was performed tons of times,
    thus slowing down the whole process with many disk reads of tens and maybe
    hundreds of MB's.

    :author: Andres Riancho (andres.riancho@gmail.com)
    """

    def __init__(
        self,
        table_prefix=None,
        dump=None,
        load=None,
        db: SQLiteDBMS | None = None,
    ):
        """
        :param table_prefix: The DBMS table prefix, mostly for debugging.
        :param dump: The function to use to serialize the object
        :param load: The function to use to deserialize the object
        :param db: The SQLite database that owns this list.
        """
        if db is None:
            raise ValueError("DiskList requires a database")
        self.db: SQLiteDBMS = db

        prefix = "" if table_prefix is None else (f"{table_prefix}_")
        self.table_name = "disk_list_" + prefix + rand_alpha(30)

        self.dump = dump
        self.load = load

        # Create table
        # DO NOT add the AUTOINCREMENT flag to the table creation since that
        # will break __getitem__ when an item is removed, see:
        #     http://www.sqlite.org/faq.html#q1
        columns = [("index_", "INTEGER"), ("eq_attrs", "TEXT"), ("pickle", "BLOB")]
        pks = ["index_"]

        self.db.create_table(self.table_name, columns, pks)
        self.db.create_index(self.table_name, ["eq_attrs"])
        self.db.commit()

        self._state = OPEN

    def cleanup(self):
        self._require_open()

        self.db.drop_table(self.table_name)
        self._state = CLOSED

    def _dump(self, obj):
        """
        Serialize an object, using the dump function provided in __init__
        or cPickle if None was specified.

        :return: A string containing the object
        """
        if self.dump is not None:
            return self.dump(obj)

        return cpickle_dumps(obj)

    def _load(self, serialized_object):
        """
        Load an object instance using the load function provided in __init__
        or cPickle if None was specified.

        :param serialized_object: The string containing the object
        :return: An instance
        """
        if self.load is not None:
            return self.load(serialized_object)

        return loads(serialized_object)

    def _get_eq_attrs_values(self, obj):
        """
        :param obj: The object from which I need a hash.

        :return: A hash representing the eq_attrs specified in the DiskItem.
        """
        attr_values = self._get_attr_values_as_builtin(obj)
        concatenated_eq_attrs = cpickle_dumps(attr_values)
        return hashlib.md5(concatenated_eq_attrs, usedforsecurity=False).hexdigest()

    def _get_attr_values_as_builtin(self, obj):
        if self._is_builtin(obj):
            return obj

        result = {}

        for attr in obj.get_eq_attrs():
            value = getattr(obj, attr)

            if not self._can_handle_attr(value):
                msg = (
                    "Complex classes like %s need to inherit from DiskItem"
                    " to be stored."
                )
                raise TypeError(msg % type(obj))

            if isinstance(value, DiskItem):
                value = self._get_attr_values_as_builtin(value)

            result[attr] = value

        return result

    def _is_builtin(self, value):
        return bool(type(value).__name__ in builtins.__dict__ or value is None)

    def _can_handle_attr(self, value):
        return bool(self._is_builtin(value) or isinstance(value, DiskItem))

    def _require_open(self):
        if self._state != OPEN:
            raise AssertionError("The DiskList is not open.")

    def __contains__(self, value):
        """
        :return: True if the value is in our list.
        """
        self._require_open()

        t = (self._get_eq_attrs_values(value),)
        # Adding the "limit 1" to the query makes it faster, as it won't
        # have to scan through all the table/index, it just stops on the
        # first match.
        query = "SELECT count(*) FROM %s WHERE eq_attrs=? LIMIT 1"
        r = self.db.select_one(query % self.table_name, t)
        return bool(r[0])

    def append(self, value):
        """
        Append a value to the DiskList.

        :param value: The value to append.
        """
        self._require_open()
        pickled_obj = self._dump(value)
        eq_attrs = self._get_eq_attrs_values(value)
        t = (eq_attrs, pickled_obj)

        query = "INSERT INTO %s VALUES (NULL, ?, ?)"
        self.db.execute(query % self.table_name, t)

    def clear(self):
        self._require_open()
        query = "DELETE FROM %s WHERE 1=1"
        self.db.execute(query % self.table_name)

    def extend(self, value_list):
        """
        Extend the disk list with a group of items that is provided in
        @value_list

        :return: None
        """
        self._require_open()
        for value in value_list:
            self.append(value)

    def ordered_iter(self, batch_size=1000, key=None):
        self._require_open()

        if batch_size <= 0:
            raise ValueError("batch_size must be greater than zero")

        # Sort bounded runs on disk and merge them to avoid retaining the full
        # list in memory while reporting large collections.
        query = "SELECT pickle FROM %s"
        results = self.db.select_in_batches(
            query % self.table_name, batch_size=batch_size
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            run_paths = []
            batch = []
            for row in results:
                batch.append(self._load(row[0]))
                if len(batch) == batch_size:
                    run_paths.append(
                        self._write_sorted_run(temp_dir, batch, len(run_paths), key=key)
                    )
                    batch = []

            if batch:
                run_paths.append(
                    self._write_sorted_run(temp_dir, batch, len(run_paths), key=key)
                )

            with ExitStack() as stack:
                run_files = [
                    stack.enter_context(open(path, "rb")) for path in run_paths
                ]
                runs = [self._read_sorted_run(run_file) for run_file in run_files]
                yield from heapq.merge(*runs, key=key)

    def _write_sorted_run(self, temp_dir, objects, run_number, key=None):
        run_path = os.path.join(temp_dir, f"run-{run_number}")
        with open(run_path, "wb") as run_file:
            for obj in sorted(objects, key=key):
                serialize_dump(obj, run_file)
        return run_path

    def _read_sorted_run(self, run_file):
        while True:
            try:
                yield serialize_load(run_file)
            except EOFError:
                return

    def __iter__(self):
        self._require_open()

        # TODO: How do I make the __iter__ thread safe?
        query = "SELECT pickle FROM %s"
        results = self.db.select_in_batches(query % self.table_name)
        for r in results:
            obj = self._load(r[0])
            yield obj

    def __reversed__(self):
        self._require_open()

        # TODO: How do I make the __iter__ thread safe?
        query = "SELECT pickle FROM %s ORDER BY index_ DESC"
        results = self.db.select_in_batches(query % self.table_name)
        for r in results:
            obj = self._load(r[0])
            yield obj

    def __getitem__(self, key):
        self._require_open()

        if isinstance(key, slice):
            return self._slice_list(key)

        # I need to add 1 to this key because the autoincrement in SQLITE
        # starts counting from 1 instead of 0
        if key >= 0:
            index_ = int(key) + 1
        else:
            # TODO: There's room for improvement in this code since we could
            # find a way to avoid the len(self) which generated one more SELECT
            # statement and is not very nice in terms of performance
            index_ = len(self) + int(key) + 1

        query = "SELECT pickle FROM %s WHERE index_ = ?"
        r = self.db.select_one(query % self.table_name, (index_,))
        if r is None:
            raise IndexError("list index out of range")

        return self._load(r[0])

    def _slice_list(self, slice_inst):
        self._require_open()

        start = slice_inst.start or 0
        stop = slice_inst.stop or len(self)
        step = slice_inst.step or 1

        copy = DiskList(db=self.db)
        disk_list_length = len(self)

        # TODO: This piece of code is VERY SLOW and can be improved. Please
        # note that for each element that's selected by the xrange/step, we'll
        # SELECT on the original list and INSERT on the copy.
        #
        # We could find ways to make this in only one SELECT/INSERT, but the
        # main problem is when I add, remove, and then try to slice a DiskList
        for i in range(start, stop, step):
            if i >= disk_list_length:
                break
            copy.append(self[i])

        return copy

    def __len__(self):
        self._require_open()

        query = "SELECT count(*) FROM %s"
        r = self.db.select_one(query % self.table_name)
        return r[0]

    def __str__(self):
        return "<DiskList [{}]>".format(", ".join([str(i) for i in self]))
