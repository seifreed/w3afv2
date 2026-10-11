"""
disk_dict.py

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

from w3af.core.data.db.dbms import SQLiteDBMS
from w3af.core.data.fuzzer.utils import rand_alpha
from w3af.core.data.misc.cpickle_dumps import cpickle_dumps
from w3af.core.data.misc.serialize import loads

_MISSING = object()


class DiskDict:
    """
    It's a dict that stores items in a sqlite3 database and has the following
    features:
        - Dict-like API
        - Is thread safe
        - Deletes the table when the instance object is deleted

    :author: Andres Riancho (andres.riancho@gmail.com)
    """

    def __init__(self, table_prefix=None, db: SQLiteDBMS | None = None):
        if db is None:
            raise ValueError("DiskDict requires a database")
        self.db: SQLiteDBMS = db

        prefix = "" if table_prefix is None else (f"{table_prefix}_")
        self.table_name = "disk_dict_" + prefix + rand_alpha(30)

        # Create table
        # DO NOT add the AUTOINCREMENT flag to the table creation since that
        # will break __getitem__ when an item is removed, see:
        #     http://www.sqlite.org/faq.html#q1
        columns = [("index_", "INTEGER"), ("key", "BLOB"), ("value", "BLOB")]
        pks = ["index_"]

        self.db.create_table(self.table_name, columns, pks)
        self.db.create_index(self.table_name, ["key"])
        self.db.commit()

    def cleanup(self):
        self.db.drop_table(self.table_name)

    def keys(self):
        query = "SELECT key FROM %s"
        pickled_keys = self.db.select_in_batches(query % self.table_name)
        result_list = []

        for r in pickled_keys:
            result_list.append(loads(r[0]))

        return result_list

    def __contains__(self, key):
        """
        :return: True if the value is in keys
        """
        # Adding the "limit 1" to the query makes it faster, as it won't
        # have to scan through all the table/index, it just stops on the
        # first match.
        query = "SELECT count(*) FROM %s WHERE key=? limit 1"
        r = self.db.select_one(query % self.table_name, (cpickle_dumps(key),))
        return bool(r[0])

    def __delitem__(self, key):
        """
        Delete the key from the dict

        :param key: The key to delete
        :return: None
        """
        query = "DELETE FROM %s WHERE key = ?"
        self.db.execute(query % self.table_name, (cpickle_dumps(key),))

    def __setitem__(self, key, value):
        # Test if it is already in the DB:
        if key in self:
            query = "UPDATE %s SET value = ? WHERE key=?"
            self.db.execute(
                query % self.table_name, (cpickle_dumps(value), cpickle_dumps(key))
            )
        else:
            query = "INSERT INTO %s VALUES (NULL, ?, ?)"
            self.db.execute(
                query % self.table_name, (cpickle_dumps(key), cpickle_dumps(value))
            )

    def __getitem__(self, key):
        query = "SELECT value FROM %s WHERE key=? limit 1"
        r = self.db.select(query % self.table_name, (cpickle_dumps(key),))

        if not r:
            args = (key, self.table_name)
            raise KeyError("{} not in {}.".format(*args))

        return loads(r[0][0])

    def __len__(self):
        query = "SELECT count(*) FROM %s"
        r = self.db.select_one(query % self.table_name)
        return r[0]

    def get(self, key, default=_MISSING):
        try:
            return self[key]
        except KeyError:
            if default is not _MISSING:
                return default

        raise KeyError()

    def pop(self, key, default=_MISSING):
        value = self.get(key, default=default)
        del self[key]
        return value
