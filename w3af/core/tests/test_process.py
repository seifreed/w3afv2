import multiprocessing
import unittest

from w3af.core.process import is_main_process


class TestIsMainProcess(unittest.TestCase):
    def test_main_process(self):
        self.assertTrue(is_main_process())

    def test_child_process(self):
        with multiprocessing.get_context("spawn").Pool(1) as process_pool:
            self.assertFalse(process_pool.apply(is_main_process))
