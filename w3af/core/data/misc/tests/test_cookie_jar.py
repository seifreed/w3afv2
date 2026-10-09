"""Tests for loading Netscape cookie files with ImprovedMozillaCookieJar."""

import os
import tempfile
import unittest
import warnings
from http.cookiejar import LoadError

from w3af.core.data.misc.cookie_jar import ImprovedMozillaCookieJar

MAGIC = "# Netscape HTTP Cookie File\n"
FUTURE = "4102444800"
PAST = "946684800"


class TestImprovedMozillaCookieJar(unittest.TestCase):
    def write_cookie_file(self, *lines, magic=MAGIC):
        handle, path = tempfile.mkstemp(suffix=".txt")
        with os.fdopen(handle, "w") as cookie_file:
            cookie_file.write(magic)
            for line in lines:
                cookie_file.write("\t".join(line) + "\n")
        self.addCleanup(os.unlink, path)
        return path

    def load(self, path, **kwargs):
        jar = ImprovedMozillaCookieJar()
        jar.load(path, **kwargs)
        return {cookie.name: cookie for cookie in jar}

    def test_load_valid_cookies(self):
        path = self.write_cookie_file(
            ("w3af.org", "FALSE", "/", "FALSE", FUTURE, "session", "123"),
            (".w3af.org", "TRUE", "/", "TRUE", FUTURE, "secure", "456"),
        )

        cookies = self.load(path)

        self.assertEqual(cookies["session"].value, "123")
        self.assertEqual(cookies["session"].expires, int(FUTURE))
        self.assertFalse(cookies["session"].secure)
        self.assertTrue(cookies["secure"].secure)
        self.assertTrue(cookies["secure"].domain_initial_dot)

    def test_comments_and_blank_lines_are_skipped(self):
        path = self.write_cookie_file(
            ("# a comment",),
            ("$ ignored",),
            ("",),
            ("w3af.org", "FALSE", "/", "FALSE", FUTURE, "session", "123"),
        )

        self.assertEqual(list(self.load(path)), ["session"])

    def test_cookie_without_name_uses_value_as_name(self):
        path = self.write_cookie_file(
            ("w3af.org", "FALSE", "/", "FALSE", FUTURE, "", "flag"),
        )

        cookie = self.load(path)["flag"]

        self.assertIsNone(cookie.value)

    def test_session_cookies_are_discarded_unless_requested(self):
        path = self.write_cookie_file(
            ("w3af.org", "FALSE", "/", "FALSE", "", "session", "123"),
        )

        self.assertEqual(self.load(path), {})
        self.assertTrue(self.load(path, ignore_discard=True)["session"].discard)

    def test_expired_cookies_are_dropped_unless_requested(self):
        path = self.write_cookie_file(
            ("w3af.org", "FALSE", "/", "FALSE", PAST, "old", "123"),
        )

        self.assertEqual(self.load(path), {})
        self.assertIn("old", self.load(path, ignore_expires=True))

    def test_invalid_magic(self):
        path = self.write_cookie_file(magic="not a cookie file\n")

        with self.assertRaisesRegex(LoadError, "does not look like a Netscape"):
            self.load(path)

    def test_wrong_number_of_fields(self):
        path = self.write_cookie_file(("w3af.org", "FALSE", "/"))

        with self.assertRaisesRegex(LoadError, "Expected seven tab delimited"):
            self.load(path)

    def test_domain_specified_without_initial_dot(self):
        path = self.write_cookie_file(
            ("w3af.org", "TRUE", "/", "FALSE", FUTURE, "session", "123"),
        )

        with self.assertRaisesRegex(LoadError, "does NOT start with a dot"):
            self.load(path)

    def test_initial_dot_without_domain_specified(self):
        path = self.write_cookie_file(
            (".w3af.org", "FALSE", "/", "FALSE", FUTURE, "session", "123"),
        )

        with self.assertRaisesRegex(LoadError, "the domain starts with a dot"):
            self.load(path)

    def test_unexpected_error_is_reported_as_load_error(self):
        path = self.write_cookie_file(
            ("w3af.org", "FALSE", "/", "FALSE", "tomorrow", "session", "123"),
        )

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            with self.assertRaisesRegex(LoadError, "invalid Netscape format"):
                self.load(path)

        self.assertIn("http.cookiejar bug!", str(caught[0].message))
