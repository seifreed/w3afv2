"""Operating system information from Python's standard library."""

import platform
import sys


def distribution_matches(name, version=None):
    if not sys.platform.startswith("linux"):
        return False

    try:
        release = platform.freedesktop_os_release()
    except OSError:
        return False

    identifiers = "{} {}".format(release.get("ID", ""), release.get("NAME", ""))
    if name.lower() not in identifiers.lower():
        return False

    return version is None or version in release.get("VERSION_ID", "")
