from unittest import TestCase

import testdata

from stockton.geo import IP
from stockton.path import Filepath


class IPTest(TestCase):
    def test_lifecycle(self):
        #raise SkipTest("This test is more for manual testing")
        ip = IP()
        self.assertTrue(ip.state)

        db = Filepath(ip.geo_path)
        self.assertTrue(db.exists())

        #pout.v(ip.state)
        #pout.v(ip.country)
        #pout.v(ip.city)

