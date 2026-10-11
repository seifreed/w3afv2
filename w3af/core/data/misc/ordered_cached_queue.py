"""
ordered_cached_queue.py

Copyright 2018 Andres Riancho

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
import queue
import uuid
from collections.abc import Callable
from typing import Any

from w3af.core.constants import POISON_PILL
from w3af.core.data.db.dbms import SQLiteDBMS, get_default_temp_db_instance
from w3af.core.data.db.disk_dict import DiskDict
from w3af.core.data.fuzzer.utils import rand_alpha
from w3af.core.data.misc.smart_queue import QueueSpeedMeasurement

LOGGER = logging.getLogger(__name__)


class _OrderedQueueIndex:
    """Keep queue ordering metadata in SQLite instead of process memory."""

    def __init__(self, db):
        self._db = db
        self._table_name = f"ordered_queue_{rand_alpha(30)}"

        columns = [("item_hash", "TEXT"), ("unique_id", "TEXT")]
        self._db.create_table(self._table_name, columns, ["unique_id"])
        self._db.create_index(self._table_name, ["item_hash", "unique_id"])

    def _query(self, statement):
        return statement.replace("{table}", self._table_name)

    def add(self, item_hash, unique_id):
        self._db.execute(
            self._query("INSERT INTO {table} VALUES (?, ?)"),
            (item_hash, unique_id),
        )

    def pop(self):
        row = self._db.select_one(
            self._query(
                "SELECT item_hash, unique_id FROM {table} "
                "ORDER BY item_hash, unique_id LIMIT 1"
            )
        )
        if row is None:
            raise IndexError("pop from empty ordered queue")

        self._db.execute(
            self._query("DELETE FROM {table} WHERE unique_id = ?"), (row[1],)
        )
        return row

    def __len__(self):
        return self._db.select_one(self._query("SELECT count(*) FROM {table}"))[0]


class OrderedCachedQueue(queue.Queue, QueueSpeedMeasurement):
    """
    This queue implements all the features explained in CachedQueue (see
    cached_queue.py) plus it will order the items in the queue as they are
    inserted.

    The queue is ordered by a unique identifier that is returned by the object
    being added. If the object is None, then it is is added to the end of the
    queue.

    The goal of this ordered queue is to impose an order in which URLs and
    forms identified by the w3af framework are processed by the plugins. Since
    plugins are run in threads, the order in which new URLs are added to the
    queue is "completely random" and depends on HTTP response times, CPU-load,
    memory swapping, etc.
    """

    LAST_SHA256_HASH = "f" * 64

    def __init__(
        self,
        maxsize=0,
        name="Unknown",
        *,
        debug_log: Callable[[str], None] | None = None,
        db: SQLiteDBMS | None = None,
    ):
        self.name = name
        self.max_in_memory = maxsize
        self._db = get_default_temp_db_instance() if db is None else db
        self.processed_tasks = 0
        self._debug_log = debug_log or LOGGER.debug

        QueueSpeedMeasurement.__init__(self)

        # We want to send zero to the maxsize of the Queue implementation
        # here because we can write an infinite number of items. But keep
        # in mind that we don't really use the queue storage in any way
        queue.Queue.__init__(self, maxsize=0)

    def get_name(self):
        return self.name

    def get_processed_tasks(self):
        return self.processed_tasks

    def _init(self, maxsize):
        """
        Initialize the dicts and pointer
        :param maxsize: The max size for the queue
        """
        self.memory: dict[str, Any] = {}
        self.disk: DiskDict = DiskDict(
            table_prefix=f"{self.name}CachedQueue", db=self._db
        )
        self.queue_order: _OrderedQueueIndex = _OrderedQueueIndex(self.disk.db)

    def _qsize(self, _len=len):
        return _len(self.memory) + _len(self.disk)

    def _get_class_name(self, obj):
        return type(obj).__name__

    def _get_hash(self, item):
        if item is None or item == POISON_PILL:
            # Place the sentinel after request hashes in lexicographic order.
            #
            # Warning! If FuzzableRequest.get_hash() ever changes its
            # implementation this will stop working as expected!
            return self.LAST_SHA256_HASH

        return item.get_hash()

    def _put(self, item):
        """
        Put a new item in the queue
        """
        #
        #   This is very useful information for finding bottlenecks in the
        #   framework / strategy
        #
        if len(self.memory) == self.max_in_memory:
            #
            #   If you see many messages like this in the scan log, then you
            #   might want to experiment with a larger maxsize for this queue
            #
            self._debug_log(
                f"OrderedCachedQueue.put() will write a {self._get_class_name(item)!r}"
                f" item to the {self.get_name()} DiskDict. This uses more CPU and disk"
                f" IO than storing in memory but will avoid high memory usage issues."
                f" The current {self.get_name()} DiskDict size is {len(self.disk)}."
            )

        #
        #   Store the ordering metadata in SQLite so the queue can grow without
        #   retaining one hash and UUID entry in process memory per item.
        #
        item_hash = self._get_hash(item)
        unique_id = str(uuid.uuid4())
        self.queue_order.add(item_hash, unique_id)

        #
        #   And now we just save the item to memory (if there is space) or
        #   disk (if it doesn't fit on memory)
        #
        if len(self.memory) < self.max_in_memory:
            self.memory[unique_id] = item
        else:
            self.disk[unique_id] = item

        self._item_added_to_queue()

    def _get(self):
        """
        Get an item from the queue
        """
        _item_hash, unique_id = self.queue_order.pop()

        try:
            item = self.memory.pop(unique_id)
        except KeyError:
            item = self.disk.pop(unique_id)

            if len(self.disk):
                #
                #   If you see many messages like this in the scan log, then you
                #   might want to experiment with a larger maxsize for this queue
                #
                self._debug_log(
                    f"OrderedCachedQueue.get() from {self.get_name()} DiskDict was used"
                    f" to read an item from disk. The current {self.get_name()} DiskDict"
                    f" size is {len(self.disk)}."
                )

        self._item_left_queue()
        self.processed_tasks += 1
        return item

    def join(self):
        """
        Blocks until all items in the Queue have been read and processed.

        The count of unfinished tasks goes up whenever an item is added to the
        queue. The count goes down whenever a consumer thread calls task_done()
        to indicate the item was retrieved and all work on it is complete.

        When the count of unfinished tasks drops to zero, join() unblocks.
        """
        self._debug_log(
            f"Called join on {self.name} with {self.unfinished_tasks} unfinished tasks"
        )

        self.all_tasks_done.acquire()
        try:
            while self.unfinished_tasks:
                result = self.all_tasks_done.wait(timeout=5)

                if not result:
                    self._debug_log(
                        f"Still have {self.unfinished_tasks} unfinished tasks in"
                        f" {self.name} join()"
                    )
        finally:
            self.all_tasks_done.release()
