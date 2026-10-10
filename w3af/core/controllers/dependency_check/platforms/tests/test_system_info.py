import tempfile
import unittest
from pathlib import Path

from w3af.core.controllers.dependency_check.platforms.system_info import (
    distribution_matches,
    parse_os_release,
    read_os_release,
)

UBUNTU_OS_RELEASE = """\
# comment line
PRETTY_NAME="Ubuntu 24.04.1 LTS"
NAME="Ubuntu"
VERSION_ID="24.04"
ID=ubuntu
ID_LIKE=debian
HOME_URL='https://www.ubuntu.com/'

not an assignment
"""


class TestParseOsRelease(unittest.TestCase):
    def test_assignments_are_parsed_and_unquoted(self):
        release = parse_os_release(UBUNTU_OS_RELEASE)

        self.assertEqual(release["NAME"], "Ubuntu")
        self.assertEqual(release["VERSION_ID"], "24.04")
        self.assertEqual(release["ID"], "ubuntu")
        self.assertEqual(release["HOME_URL"], "https://www.ubuntu.com/")
        self.assertEqual(release["PRETTY_NAME"], "Ubuntu 24.04.1 LTS")

    def test_comments_and_garbage_are_ignored(self):
        release = parse_os_release(UBUNTU_OS_RELEASE)

        self.assertNotIn("# comment line", release)
        self.assertNotIn("not an assignment", release)
        self.assertEqual(len(release), 6)

    def test_empty_text_has_no_assignments(self):
        self.assertEqual(parse_os_release(""), {})

    def test_commented_assignment_is_ignored(self):
        self.assertEqual(parse_os_release("#ID=fedora\n"), {})


class OsReleaseFilesTestCase(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)

    def write(self, name, text):
        path = self.directory / name
        path.write_text(text)
        return str(path)

    def missing(self, name):
        return str(self.directory / name)


class TestReadOsRelease(OsReleaseFilesTestCase):
    def test_first_readable_file_is_used(self):
        paths = (
            self.missing("absent"),
            self.write("first", "ID=fedora\n"),
            self.write("second", "ID=ubuntu\n"),
        )

        self.assertEqual(read_os_release(paths), {"ID": "fedora"})

    def test_no_readable_file_gives_an_empty_release(self):
        self.assertEqual(read_os_release((self.missing("a"), self.missing("b"))), {})

    def test_default_paths_never_fail(self):
        self.assertIsInstance(read_os_release(), dict)


class TestDistributionMatches(OsReleaseFilesTestCase):
    def setUp(self):
        super().setUp()
        self.paths = (self.write("os-release", UBUNTU_OS_RELEASE),)

    def test_matches_by_id_or_name_ignoring_case(self):
        self.assertTrue(distribution_matches("ubuntu", paths=self.paths))
        self.assertTrue(distribution_matches("UBUNTU", paths=self.paths))

    def test_other_distribution_does_not_match(self):
        self.assertFalse(distribution_matches("fedora", paths=self.paths))

    def test_version_must_be_contained_in_version_id(self):
        self.assertTrue(distribution_matches("ubuntu", "24.04", self.paths))
        self.assertFalse(distribution_matches("ubuntu", "18.04", self.paths))

    def test_nothing_matches_without_os_release_file(self):
        self.assertFalse(
            distribution_matches("ubuntu", paths=(self.missing("absent"),))
        )
