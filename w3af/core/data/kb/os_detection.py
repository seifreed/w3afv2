"""Remote operating-system detection policies used by shell models."""

from w3af.core.exceptions import BaseFrameworkException, OSDetectionException


def _read_remote_files(remote_read, paths):
    try:
        return tuple(remote_read(path) for path in paths)
    except (BaseFrameworkException, OSError):
        return None


def detect_remote_os(remote_read):
    """Detect Linux or Windows by reading characteristic remote files."""
    linux_files = _read_remote_files(
        remote_read,
        ("/etc/passwd", "/etc/mtab", "/proc/sys/kernel/ostype"),
    )
    if linux_files is not None:
        passwd, mounts, kernel_type = linux_files
        if "/bin/" in passwd or "rw" in mounts or "linux" in kernel_type.lower():
            return "linux"

    windows_files = _read_remote_files(
        remote_read,
        (
            "%SYSTEMROOT%\\win.ini",
            "C:\\windows\\win.ini",
            "C:\\win32\\win.ini",
            "C:\\win\\win.ini",
        ),
    )
    if windows_files is not None and "[fonts]" in "".join(windows_files):
        return "windows"

    raise OSDetectionException("Failed to get/identify the remote OS.")
