from unittest import TestCase as BaseTestCase, SkipTest
import os


class TestCase(BaseTestCase):
    @classmethod
    def setUpClass(cls):
        if os.environ["USER"] != "root":
            raise RuntimeError("User is not root, re-run this test with sudo")

