from unittest import TestCase
import time

import testdata

from stockton.path import Dirpath, Filepath


def setUpModule():
    pass


def tearDownModule():
    pass


class FilepathTest(TestCase):
    def test_modified_within(self):
        f = Filepath.create_temp(testdata.get_ascii(32))
        self.assertTrue(f.modified_within(5))
        self.assertTrue(f.modified_within(days=1))
        time.sleep(1.1)
        self.assertFalse(f.modified_within(1))

