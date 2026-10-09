"""
log_handler.py

Copyright 2015 Andres Riancho

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

import contextlib
import dbm.dumb
import json
import os
import tempfile
import threading
import time
from collections.abc import Iterator
from typing import Any

from w3af.core.controllers.plugins.output_plugin import OutputPlugin
from w3af.core.data.constants.severity import MEDIUM

DEBUG = "debug"
INFORMATION = "information"
ERROR = "error"
VULNERABILITY = "vulnerability"
CONSOLE = "console"
LOG_HTTP = "log_http"

DATABASE_FILE_SUFFIXES = (".dat", ".dir", ".bak")


class RESTAPIOutput(OutputPlugin):
    """
    Store all log messages, serialized as JSON, on a disk database

    The database uses the pure Python dbm.dumb backend because messages are
    written by the output manager thread and read by the REST API threads, and
    the sqlite3 backend can only be used from the thread that opened it.

    :author: Andres Riancho (andres.riancho@gmail.com)
    """

    def __init__(self) -> None:
        super().__init__()

        self._db_backend: str | None = None
        self._log_id = -1
        self._lock = threading.RLock()

        # Using a dbm database instead of a DiskList to make sure we don't
        # depend on anything related with w3af, DiskList uses DBMS which is
        # cleared and (ab)used by the framework
        #
        # https://github.com/andresriancho/w3af/issues/11214
        self._resources = contextlib.ExitStack()
        self.log = self._open_database()

    def _open_database(self) -> Any:
        return self._resources.enter_context(dbm.dumb.open(self.get_db_backend(), "c"))

    def get_db_backend(self) -> str:
        if self._db_backend is None:
            fd, self._db_backend = tempfile.mkstemp(prefix="w3af-api-log", suffix="db")
            os.close(fd)
            os.unlink(self._db_backend)

        return self._db_backend

    def cleanup(self) -> None:
        with self._lock:
            self._resources.close()

        for suffix in DATABASE_FILE_SUFFIXES:
            with contextlib.suppress(FileNotFoundError):
                os.unlink(self.get_db_backend() + suffix)

    def get_log_id(self) -> str:
        self._log_id += 1
        return str(self._log_id)

    def __len__(self) -> int:
        with self._lock:
            return len(self.log)

    def get_entries(self, start: int, end: int) -> Iterator["Message"]:
        with self._lock:
            entries = []
            for log_id in range(start, end):
                record = self.log.get(str(log_id))
                if record is None:
                    break
                entries.append(Message.from_record(json.loads(record)))

        yield from entries

    def _store(self, msg_type: str, msg_string: Any, severity: Any = None) -> None:
        with self._lock:
            _id = self.get_log_id()
            message = Message(msg_type, self._clean_string(msg_string), _id)
            message.set_severity(severity)
            self.log[_id] = json.dumps(message.to_record())

    def debug(self, msg_string: Any, new_line: bool = True) -> None:
        """
        This method is called from the output object. The output object was
        called from a plugin or from the framework. This method should take an
        action for debug messages.
        """
        self._store(DEBUG, msg_string)

    def information(self, msg_string: Any, new_line: bool = True) -> None:
        """
        This method is called from the output object. The output object was
        called from a plugin or from the framework. This method should take an
        action for informational messages.
        """
        self._store(INFORMATION, msg_string)

    def error(self, msg_string: Any, new_line: bool = True) -> None:
        """
        This method is called from the output object. The output object was
        called from a plugin or from the framework. This method should take an
        action for error messages.
        """
        self._store(ERROR, msg_string)

    def vulnerability(
        self, msg_string: Any, new_line: bool = True, severity: Any = MEDIUM
    ) -> None:
        """
        This method is called from the output object. The output object was
        called from a plugin or from the framework. This method should take an
        action when a vulnerability is found.
        """
        self._store(VULNERABILITY, msg_string, severity)

    def console(self, msg_string: Any, new_line: bool = True) -> None:
        """
        This method is used by the w3af console to print messages to the outside
        """
        self._store(CONSOLE, msg_string)


class Message:
    def __init__(self, msg_type, msg, _id):
        """
        :param msg_type: console, information, vulnerability, etc
        :param msg: The message itself
        """
        self._type = msg_type
        self._msg = msg
        self._time = time.time()
        self._severity = None
        self._id = int(_id)

    def get_id(self):
        return self._id

    def get_severity(self):
        return self._severity

    def set_severity(self, the_severity):
        self._severity = the_severity

    def get_msg(self):
        return self._msg

    def get_type(self):
        return self._type

    def get_real_time(self):
        return self._time

    def get_time(self):
        return time.strftime("%c", time.localtime(self._time))

    def to_record(self):
        """
        :return: The message attributes, as stored in the log database
        """
        return {
            "type": self._type,
            "message": self._msg,
            "time": self._time,
            "severity": self._severity,
            "id": self._id,
        }

    @classmethod
    def from_record(cls, record):
        message = cls(record["type"], record["message"], record["id"])
        message._time = record["time"]
        message.set_severity(record["severity"])
        return message

    def to_json(self):
        return {
            "type": self._type,
            "message": self._msg,
            "time": self.get_time(),
            "severity": self.get_severity(),
            "id": self.get_id(),
        }
