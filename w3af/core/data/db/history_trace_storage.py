"""Read and write request/response history traces."""

import logging
import os
import time
import zipfile

from w3af.core.data.db.exceptions import DBException
from w3af.core.data.db.history_trace_serializer import (
    HistoryTraceSerializer,
    TraceReadException,
)
from w3af.core.data.url.http_request import HTTPRequest
from w3af.core.data.url.http_response import HTTPResponse

LOGGER = logging.getLogger(__name__)


def get_zip_id_range(zip_file: str) -> tuple[int, int]:
    """Return the trace ID range encoded in a ZIP filename."""
    name = os.path.basename(zip_file).split(".")[0]
    start, end = name.split("-")
    return int(start), int(end)


class HistoryTraceStorage:
    """Persist serialized traces as files or entries in ZIP archives."""

    def __init__(self, session_dir: str, serializer: HistoryTraceSerializer) -> None:
        self._session_dir = session_dir
        self._serializer = serializer

    def get_trace_filename(self, trace_id: int) -> str:
        return os.path.join(self._session_dir, f"{trace_id}.trace")

    def save_trace(
        self, request: HTTPRequest, response: HTTPResponse, trace_id: int
    ) -> None:
        path = self.get_trace_filename(trace_id)
        serialized_trace = self._serializer.serialize(request, response)

        try:
            with open(path, "wb") as trace_file:
                trace_file.write(serialized_trace)
        except OSError:
            self._raise_if_trace_directory_missing(path)
            raise

    def load_from_string(
        self, serialized_trace: bytes
    ) -> tuple[HTTPRequest, HTTPResponse]:
        return self._serializer.deserialize(serialized_trace)

    def load_from_trace_file(self, trace_id: int) -> tuple[HTTPRequest, HTTPResponse]:
        file_name = self.get_trace_filename(trace_id)

        if not os.path.exists(file_name):
            raise TraceReadException(f"Trace file {file_name} does not exist")

        with open(file_name, "rb") as trace_file:
            serialized_trace = trace_file.read()
        return self.load_from_string(serialized_trace)

    def load_from_trace_file_concurrent(
        self, trace_id: int
    ) -> tuple[HTTPRequest, HTTPResponse]:
        wait_time = 0.05

        for _ in range(int(1 / wait_time)):
            try:
                return self.load_from_trace_file(trace_id)
            except TraceReadException as error:
                LOGGER.debug('Failed to read trace file %s: "%s"', trace_id, error)
                time.sleep(wait_time)

        file_name = self.get_trace_filename(trace_id)
        raise DBException(f'Timeout expecting trace file "{file_name}" to be ready')

    def load_from_file(self, trace_id: int) -> tuple[HTTPRequest, HTTPResponse]:
        file_name = self.get_trace_filename(trace_id)

        if not os.path.exists(file_name):
            try:
                return self.load_from_zip(trace_id)
            except TraceReadException as error:
                LOGGER.debug(
                    'Failed to load trace %s from zip file: "%s"', trace_id, error
                )

            if not os.path.exists(file_name):
                raise TraceReadException(f"No zip nor trace file for ID {trace_id}")

        return self.load_from_trace_file_concurrent(trace_id)

    def load_from_zip(self, trace_id: int) -> tuple[HTTPRequest, HTTPResponse]:
        files = [
            filename
            for filename in os.listdir(self._session_dir)
            if filename.endswith(".zip")
        ]

        for zip_file in files:
            start, end = get_zip_id_range(zip_file)
            if start <= trace_id <= end:
                return self.load_from_zip_file(trace_id, zip_file)

        raise TraceReadException(f"No zip file contains {trace_id}")

    def load_from_zip_file(
        self, trace_id: int, zip_file: str
    ) -> tuple[HTTPRequest, HTTPResponse]:
        try:
            archive = zipfile.ZipFile(os.path.join(self._session_dir, zip_file))
        except zipfile.BadZipfile:
            raise TraceReadException(f"Zip file {zip_file} has an invalid format")

        try:
            serialized_trace = archive.read(f"{trace_id}.trace")
        except KeyError:
            raise TraceReadException(
                f"Zip file {zip_file} does not contain ID {trace_id}"
            )

        return self.load_from_string(serialized_trace)

    @staticmethod
    def _raise_if_trace_directory_missing(path: str) -> None:
        missing = None
        directory = os.path.dirname(path)

        while directory and not os.path.exists(directory):
            missing = directory
            directory = os.path.dirname(directory)

        if missing is not None:
            msg = (
                'Directory does not exist: "%s" while trying to'
                ' write DB history to "%s"'
            )
            raise OSError(msg % (missing, path))
