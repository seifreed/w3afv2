"""Queue and compress history trace files."""

import os
import threading
import zipfile
from dataclasses import dataclass


@dataclass(frozen=True)
class PendingCompressionJob:
    """A contiguous range of trace identifiers waiting for compression."""

    start: int
    end: int


def get_trace_id(trace_file: str) -> int:
    """Return the numeric identifier encoded in a trace filename."""
    return int(os.path.basename(trace_file).rsplit(".")[-2])


class HistoryTraceCompressor:
    """Coordinate shared trace compression jobs for all history instances."""

    _EXTENSION = "trace"
    _TMP_EXTENSION = "tmp"
    _COMPRESSED_EXTENSION = "zip"
    _COMPRESSED_FILE_BATCH = 150
    _UNCOMPRESSED_FILES = 50
    _MIN_FILE_COUNT = _COMPRESSED_FILE_BATCH + _UNCOMPRESSED_FILES

    def __init__(self, session_dir: str) -> None:
        self._session_dir = session_dir
        self._pending_compression_jobs: list[PendingCompressionJob] = []
        self._latest_compression_job_end = 0
        self._compression_lock = threading.RLock()

    def get_pending_job(self) -> PendingCompressionJob | None:
        with self._compression_lock:
            try:
                return self._pending_compression_jobs.pop(0)
            except IndexError:
                return None

    def queue(self, response_id: int) -> None:
        """Queue complete batches while retaining the newest trace files."""
        if response_id % 100 != 0:
            return

        with self._compression_lock:
            files = [
                os.path.join(self._session_dir, filename)
                for filename in os.listdir(self._session_dir)
                if filename.endswith(self._EXTENSION)
            ]

            if len(files) <= self._MIN_FILE_COUNT:
                return

            files.sort(key=get_trace_id)
            files = files[: -self._UNCOMPRESSED_FILES]

            while len(files) >= self._COMPRESSED_FILE_BATCH:
                current_batch_files = files[: self._COMPRESSED_FILE_BATCH]
                start = get_trace_id(current_batch_files[0])
                end = get_trace_id(current_batch_files[-1])

                if start <= self._latest_compression_job_end:
                    break

                self._pending_compression_jobs.append(PendingCompressionJob(start, end))
                self._latest_compression_job_end = end
                files = files[self._COMPRESSED_FILE_BATCH :]

    def process(self, pending_compression: PendingCompressionJob) -> None:
        """Write one pending batch atomically and remove its source traces."""
        trace_range = range(pending_compression.start, pending_compression.end + 1)
        files = [
            os.path.join(self._session_dir, f"{trace_id}.{self._EXTENSION}")
            for trace_id in trace_range
        ]

        compressed_filename = os.path.join(
            self._session_dir,
            f"{pending_compression.start}-{pending_compression.end}."
            f"{self._COMPRESSED_EXTENSION}",
        )
        compressed_filename_temp = f"{compressed_filename}.{self._TMP_EXTENSION}"

        compressed = zipfile.ZipFile(
            file=compressed_filename_temp,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
        )
        for filename in files:
            try:
                compressed.write(
                    filename=filename,
                    arcname=f"{get_trace_id(filename)}.{self._EXTENSION}",
                )
            except OSError:
                continue
        compressed.close()

        os.rename(compressed_filename_temp, compressed_filename)

        for filename in files:
            try:
                os.remove(filename)
            except OSError:
                continue
