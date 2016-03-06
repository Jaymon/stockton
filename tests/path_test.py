from unittest import TestCase
import time

import testdata

from stockton.path import Dirpath, Filepath, Sentinal


def setUpModule():
    pass


def tearDownModule():
    pass


class SentinalTest(TestCase):
    def test_exists(self):
        s = Sentinal(testdata.get_ascii())
        self.assertFalse(s.exists())

        s.create()
        self.assertTrue(s.exists())

    def test_with(self):
        name = testdata.get_ascii()
        with Sentinal.check(name) as execute:
            self.assertFalse(execute)

        s = Sentinal(name)
        self.assertTrue(s)

class FilepathTest(TestCase):
    def test_modified_within(self):
        f = Filepath.create_temp(testdata.get_ascii(32))
        self.assertTrue(f.modified_within(5))
        self.assertTrue(f.modified_within(days=1))
        time.sleep(1.1)
        self.assertFalse(f.modified_within(1))

