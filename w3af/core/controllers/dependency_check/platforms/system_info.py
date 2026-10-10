"""Operating system information from the freedesktop os-release files."""

from pathlib import Path

OS_RELEASE_PATHS = ("/etc/os-release", "/usr/lib/os-release")


def parse_os_release(text):
    """
    :param text: The contents of an os-release file
    :return: A dict with the KEY=value assignments found in it
    """
    release = {}

    for line in text.splitlines():
        key, separator, value = line.strip().partition("=")
        if separator and not key.startswith("#"):
            release[key] = value.strip("\"'")

    return release


def read_os_release(paths=OS_RELEASE_PATHS):
    """
    :return: The parsed contents of the first readable os-release file, an
             empty dict if there is none (Windows, macOS)
    """
    for path in paths:
        try:
            return parse_os_release(Path(path).read_text(encoding="utf-8"))
        except OSError:
            continue

    return {}


def distribution_matches(name, version=None, paths=OS_RELEASE_PATHS):
    release = read_os_release(paths)
    identifiers = "{} {}".format(release.get("ID", ""), release.get("NAME", ""))
    if name.lower() not in identifiers.lower():
        return False

    return version is None or version in release.get("VERSION_ID", "")
