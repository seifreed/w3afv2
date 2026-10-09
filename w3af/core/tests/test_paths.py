import os
import unittest

from w3af.core.paths import HOME_DIR, get_home_dir


class TestHomeDirectory(unittest.TestCase):
    def test_default_home_directory(self):
        configured_home = os.environ.pop("W3AF_HOME_DIR", None)
        try:
            self.assertEqual(get_home_dir(), HOME_DIR)
        finally:
            if configured_home is not None:
                os.environ["W3AF_HOME_DIR"] = configured_home

    def test_environment_override(self):
        configured_home = os.environ.get("W3AF_HOME_DIR")
        home_override = os.path.join(os.getcwd(), "w3af-home-test")
        try:
            os.environ["W3AF_HOME_DIR"] = home_override
            self.assertEqual(get_home_dir(), home_override)
        finally:
            if configured_home is None:
                os.environ.pop("W3AF_HOME_DIR", None)
            else:
                os.environ["W3AF_HOME_DIR"] = configured_home
