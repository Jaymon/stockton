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
    def test_create(self):
        d = testdata.create_dir()
        fex = testdata.create_file("create_exists", "foo", d)
        f = Filepath(fex)
        self.assertTrue(f.exists())
        f.create()
        self.assertTrue("foo" in f.lines())

        f = Filepath(d, "create_not_exists")
        self.assertFalse(f.exists())
        f.create()
        self.assertTrue(f.exists())
        self.assertFalse("foo" in f.lines())

    def test_checksum(self):
        f = Filepath.create_temp(testdata.get_uuid())
        checksum = f.checksum
        f.write("foo")
        checksum2 = f.checksum
        self.assertNotEqual(checksum, checksum2)

        f.write("bar")
        time.sleep(0.1)
        checksum3 = f.checksum
        self.assertNotEqual(checksum, checksum3)
        self.assertNotEqual(checksum2, checksum3)

    def test_delete_lines(self):
        f = Filepath.create_temp("delete_lines")
        f.writelines([
            "foo",
            "foo",
            "bar",
            "foo"
        ])

        count = f.delete_lines("bar")
        self.assertEqual(1, count)
        self.assertEqual(3, len(list(f.lines())))
        self.assertFalse("bar" in f.contents())

        f = Filepath.create_temp("delete_lines_todelete")
        f.writelines([
            "todelete.com default._domainkey.todelete.com",
            ""
        ])
        count = f.delete_lines("todelete.com")
        self.assertEqual(1, count)
        self.assertFalse(f.contains("todelete.com"))


    def test_modified_within(self):
        f = Filepath.create_temp(testdata.get_ascii(32))
        self.assertTrue(f.modified_within(5))
        self.assertTrue(f.modified_within(days=1))
        time.sleep(1.1)
        self.assertFalse(f.modified_within(1))

