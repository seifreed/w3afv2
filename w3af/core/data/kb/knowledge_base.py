"""
knowledge_base.py

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

import functools
from collections.abc import Iterable
from typing import ClassVar

from w3af.core.data.constants.severity import HIGH, INFORMATION, LOW, MEDIUM
from w3af.core.data.db.dbms import get_default_persistent_db_instance
from w3af.core.data.db.disk_set import DiskSet
from w3af.core.data.db.exceptions import DBException
from w3af.core.data.fuzzer.utils import rand_alpha
from w3af.core.data.kb.base import BasicKnowledgeBase
from w3af.core.data.kb.info import Info
from w3af.core.data.kb.info_set import InfoSet
from w3af.core.data.kb.shell import Shell
from w3af.core.data.misc.cpickle_dumps import cpickle_dumps
from w3af.core.data.misc.serialize import loads
from w3af.core.data.parsers.doc.url import URL
from w3af.core.data.request.fuzzable_request import FuzzableRequest


def requires_setup(_method):
    @functools.wraps(_method)
    def decorated(self, *args, **kwargs):
        if not self.initialized:
            self.setup()

        return _method(self, *args, **kwargs)

    return decorated


class DBKnowledgeBase(BasicKnowledgeBase):
    """
    This class saves the data that is sent to it by plugins. It is the only way
    in which plugins can exchange information.

    Data is stored in a DB.

    :author: Andres Riancho (andres.riancho@gmail.com)
    """

    COLUMNS: ClassVar[list[tuple[str, str]]] = [
        ("location_a", "TEXT"),
        ("location_b", "TEXT"),
        ("uniq_id", "TEXT"),
        ("pickle", "BLOB"),
    ]

    def __init__(self, db=None):
        super().__init__()
        self.initialized = False
        self._db = db

    def setup(self):
        """
        Setup all the required backend stores. This was mostly created to avoid
        starting any threads during __init__() which is called during python's
        import phase and dead-locks in some cases.

        :return: None
        """
        with self._kb_lock:
            if self.initialized:
                return

            self.db = self._db or get_default_persistent_db_instance()
            self.urls = DiskSet(table_prefix="kb_urls", db=self.db)
            self.fuzzable_requests = DiskSet(
                table_prefix="kb_fuzzable_requests", db=self.db
            )

            self.table_name = "knowledge_base_" + rand_alpha(30)
            self.db.create_table(self.table_name, self.COLUMNS)
            self.db.create_index(self.table_name, ["location_a", "location_b"])
            self.db.create_index(self.table_name, ["uniq_id"])
            self.db.commit()

            # Only initialize once
            self.initialized = True

    @requires_setup
    def clear(self, location_a, location_b):
        location_a = self._get_real_name(location_a)

        query = "DELETE FROM %s WHERE location_a = ? and location_b = ?"
        params = (location_a, location_b)
        with self._kb_lock:
            self.db.execute(query % self.table_name, params)
            cache = self._reached_max_info_instances_cache
            for key in cache:
                if key[:2] == (location_a, location_b):
                    del cache[key]

    @requires_setup
    def raw_write(self, location_a, location_b, value):
        """
        This method saves value to (location_a,location_b) but previously
        clears any pre-existing values.
        """
        if isinstance(value, Info):
            raise TypeError("Use append or append_uniq to store vulnerabilities")

        location_a = self._get_real_name(location_a)

        self.clear(location_a, location_b)
        self.append(location_a, location_b, value, ignore_type=True)

    @requires_setup
    def raw_read(self, location_a, location_b):
        """
        This method reads the value from (location_a, location_b)
        """
        location_a = self._get_real_name(location_a)
        result = self.get(location_a, location_b, check_types=False)

        if len(result) > 1:
            msg = "Incorrect use of raw_write/raw_read, found %s results."
            raise RuntimeError(msg % len(result))
        elif len(result) == 0:
            return []
        else:
            return result[0]

    def _get_uniq_id(self, obj):
        if isinstance(obj, (Info, InfoSet, Shell)):
            return obj.get_uniq_id()

        if isinstance(obj, Iterable):
            concat_all = "".join([str(hash(i)) for i in obj])
            return str(hash(concat_all))

        return str(hash(obj))

    @requires_setup
    def append(self, location_a, location_b, value, ignore_type=False):
        """
        This method appends the location_b value to a dict.
        """
        if not ignore_type and not isinstance(value, (Info, Shell, InfoSet)):
            msg = (
                "You MUST use raw_write/raw_read to store non-info objects"
                " to the KnowledgeBase."
            )
            raise TypeError(msg)

        location_a = self._get_real_name(location_a)
        uniq_id = self._get_uniq_id(value)

        pickled_obj = cpickle_dumps(value)
        t = (location_a, location_b, uniq_id, pickled_obj)

        query = "INSERT INTO %s VALUES (?, ?, ?, ?)"
        self.db.execute(query % self.table_name, t)

    @requires_setup
    def get(self, location_a, location_b, check_types=True):
        """
        :param location_a: The plugin that saved the data to the
                           kb.info Typically the name of the plugin,
                           but could also be the plugin instance.

        :param location_b: The name of the variables under which the vuln
                           objects were saved. Typically the same name of
                           the plugin, or something like "vulns", "errors",
                           etc. In most cases this is NOT None. When set
                           to None, a dict with all the vuln objects found
                           by the plugin_name is returned.

        :return: Returns the data that was saved by another plugin.
        """
        return list(self.get_iter(location_a, location_b, check_types=check_types))

    @requires_setup
    def get_iter(self, location_a, location_b, check_types=True):
        """
        Same as get() but yields items one by one instead of returning
        a list with all the items.
        """
        location_a = self._get_real_name(location_a)

        if location_b is None:
            query = "SELECT pickle FROM %s WHERE location_a = ?"
            params = (location_a,)
        else:
            query = "SELECT pickle FROM %s WHERE location_a = ?" " and location_b = ?"
            params = (location_a, location_b)

        for r in self.db.select_in_batches(query % self.table_name, params):
            obj = loads(r[0])

            if check_types and not isinstance(obj, (Info, InfoSet, Shell)):
                raise TypeError(
                    "Use raw_write and raw_read to query the"
                    " knowledge base for non-Info objects"
                )

            yield obj

    @requires_setup
    def get_all_uniq_ids_iter(self, include_ids=()):
        """
        :param include_ids: If specified, only include these IDs.
        :yield: All uniq IDs from the KB
        """
        if include_ids:
            bindings = ["?"] * len(include_ids)
            bindings = ",".join(bindings)
            query = "SELECT uniq_id FROM %s WHERE uniq_id IN (%s)"
            query %= (self.table_name, bindings)

            result = self.db.select_in_batches(query, parameters=include_ids)

        else:
            query = "SELECT uniq_id FROM %s"
            result = self.db.select_in_batches(query % self.table_name)

        for (uniq_id,) in result:
            yield uniq_id

    @requires_setup
    def update(self, old_info, update_info):
        """
        :param old_info: The info/vuln instance to be updated in the kb.
        :param update_info: The info/vuln instance with new information
        :return: Nothing
        """
        old_not_info = not isinstance(old_info, (Info, InfoSet, Shell))
        update_not_info = not isinstance(update_info, (Info, InfoSet, Shell))

        if old_not_info or update_not_info:
            msg = (
                "You MUST use raw_write/raw_read to store non-info objects"
                " to the KnowledgeBase."
            )
            raise TypeError(msg)

        old_uniq_id = old_info.get_uniq_id()
        new_uniq_id = update_info.get_uniq_id()
        pickled = cpickle_dumps(update_info)

        # Update the pickle and unique_id after finding by original uniq_id
        query = "UPDATE %s SET pickle = ?, uniq_id = ? WHERE uniq_id = ?"

        params = (pickled, new_uniq_id, old_uniq_id)
        result = self.db.execute(query % self.table_name, params).result()

        if not result.rowcount:
            ex = (
                "Failed to update() %s instance because"
                " the original unique_id (%s) does not exist in the DB,"
                " or the new unique_id (%s) is invalid."
            )
            raise DBException(
                ex % (old_info.__class__.__name__, old_uniq_id, new_uniq_id)
            )

    @requires_setup
    def get_all_entries_of_class(self, klass, exclude_ids=()):
        """
        :return: A list of all objects where class in klass that are saved in the
                 kb.
        """
        return list(self.get_all_entries_of_class_iter(klass, exclude_ids=exclude_ids))

    @requires_setup
    def get_all_entries_of_class_iter(self, klass, exclude_ids=()):
        """
        :yield: All objects where class in klass that are saved in the kb.
        """
        bindings = ["?"] * len(exclude_ids)
        bindings = ",".join(bindings)
        query = "SELECT uniq_id, pickle FROM %s WHERE uniq_id NOT IN (%s)"
        query %= (self.table_name, bindings)

        results = self.db.select_in_batches(query, parameters=exclude_ids)

        for (
            uniq_id,
            serialized_obj,
        ) in results:
            obj = loads(serialized_obj)
            if isinstance(obj, klass):
                yield obj

    @requires_setup
    def get_all_vulns(self):
        """
        :return: A list of all info instances with severity in (LOW, MEDIUM,
                 HIGH)
        """
        return self._get_all_by_severity((LOW, MEDIUM, HIGH))

    @requires_setup
    def get_all_infos(self):
        """
        :return: A list of all info instances with severity eq INFORMATION
        """
        return self._get_all_by_severity((INFORMATION,))

    def _get_all_by_severity(self, severities):
        query = "SELECT pickle FROM %s"
        results = self.db.select_in_batches(query % self.table_name)

        result_lst = []

        for r in results:
            obj = loads(r[0])
            if hasattr(obj, "get_severity"):
                severity = obj.get_severity()
                if severity in severities:
                    result_lst.append(obj)

        return result_lst

    @requires_setup
    def cleanup(self):
        """
        Cleanup internal data.
        """
        with self._kb_lock:
            query = "DELETE FROM %s WHERE 1=1"
            self.db.execute(query % self.table_name)
            self._reached_max_info_instances_cache.clear()

            # Remove the old, create new.
            old_urls = self.urls
            self.urls = DiskSet(table_prefix="kb_urls", db=self.db)
            old_urls.cleanup()

            old_fuzzable_requests = self.fuzzable_requests
            self.fuzzable_requests = DiskSet(
                table_prefix="kb_fuzzable_requests", db=self.db
            )
            old_fuzzable_requests.cleanup()

    @requires_setup
    def get_all_known_urls(self):
        """
        :return: A DiskSet with all the known URLs as URL objects.
        """
        return self.urls

    @requires_setup
    def add_url(self, url):
        """
        :return: True if the URL was previously unknown
        """
        if not isinstance(url, URL):
            msg = "add_url requires a URL as parameter got %s instead."
            raise TypeError(msg % type(url))

        return self.urls.add(url)

    @requires_setup
    def get_all_known_fuzzable_requests(self):
        """
        :return: A DiskSet with all the known URLs as URL objects.
        """
        return self.fuzzable_requests

    @requires_setup
    def add_fuzzable_request(self, fuzzable_request):
        """
        :return: True if the FuzzableRequest was previously unknown
        """
        if not isinstance(fuzzable_request, FuzzableRequest):
            msg = (
                "add_fuzzable_request requires a FuzzableRequest as"
                ' parameter, got "%s" instead.'
            )
            raise TypeError(msg % type(fuzzable_request))

        self.add_url(fuzzable_request.get_url())
        return self.fuzzable_requests.add(fuzzable_request)
