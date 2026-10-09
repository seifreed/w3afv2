import tempfile
import unittest
from pathlib import Path

from w3af.core.data.kb.os_detection import detect_remote_os
from w3af.core.exceptions import OSDetectionException

REMOTE_FILES = (
    "/etc/passwd",
    "/etc/mtab",
    "/proc/sys/kernel/ostype",
    "%SYSTEMROOT%\\win.ini",
    "C:\\windows\\win.ini",
    "C:\\win32\\win.ini",
    "C:\\win\\win.ini",
)


def remote_file_reader(directory, contents, missing=()):
    paths = {}
    for index, remote_path in enumerate(REMOTE_FILES):
        local_path = Path(directory, str(index))
        if remote_path not in missing:
            local_path.write_text(contents.get(remote_path, ""), encoding="utf-8")
        paths[remote_path] = local_path

    def read_remote_file(remote_path):
        return paths[remote_path].read_text(encoding="utf-8")

    return read_remote_file


class TestRemoteOSDetection(unittest.TestCase):
    def test_detects_linux_from_kernel_type(self):
        with tempfile.TemporaryDirectory() as directory:
            read_remote_file = remote_file_reader(
                directory, {"/proc/sys/kernel/ostype": "Linux"}
            )

            self.assertEqual(detect_remote_os(read_remote_file), "linux")

    def test_detects_windows_from_ini_file(self):
        with tempfile.TemporaryDirectory() as directory:
            read_remote_file = remote_file_reader(
                directory, {"C:\\windows\\win.ini": "[fonts]"}
            )

            self.assertEqual(detect_remote_os(read_remote_file), "windows")

    def test_raises_when_os_is_unknown(self):
        with tempfile.TemporaryDirectory() as directory:
            read_remote_file = remote_file_reader(directory, {})
            with self.assertRaises(OSDetectionException):
                detect_remote_os(read_remote_file)

    def test_raises_when_remote_reads_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            read_remote_file = remote_file_reader(directory, {}, missing=REMOTE_FILES)
            with self.assertRaises(OSDetectionException):
                detect_remote_os(read_remote_file)
