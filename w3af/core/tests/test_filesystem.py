import os
import stat
import unittest

from w3af.core.filesystem import create_temp_dir, get_temp_dir, remove_temp_dir


class TestTempDir(unittest.TestCase):
    def setUp(self):
        # Other tests rely on the process temporary directory existing
        self.addCleanup(create_temp_dir)

    def test_temp_dir_is_process_specific(self):
        self.assertEqual(os.path.basename(get_temp_dir()), str(os.getpid()))

    def test_create_remove_cycle(self):
        remove_temp_dir(ignore_errors=True)
        self.assertFalse(os.path.exists(get_temp_dir()))

        created = create_temp_dir()

        self.assertEqual(created, get_temp_dir())
        self.assertEqual(stat.S_IMODE(os.stat(created).st_mode), stat.S_IRWXU)

    def test_create_is_idempotent(self):
        self.assertEqual(create_temp_dir(), create_temp_dir())

    def test_remove_missing_dir_without_ignoring_errors(self):
        remove_temp_dir(ignore_errors=True)

        self.assertRaises(FileNotFoundError, remove_temp_dir)
