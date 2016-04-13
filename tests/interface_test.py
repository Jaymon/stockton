from unittest import TestCase, SkipTest
import os

import testdata

#from stockton.dns import Domain
#from stockton.path import Filepath, Dirpath

from stockton.interface.dkim import DKIM


def setUpModule():
    if os.environ["USER"] != "root":
        raise RuntimeError("User is not root, re-run this test with sudo")


class DKIMTest(TestCase):
    @classmethod
    def setUpClass(cls):
        d = DKIM()
        d.install()

    def test_domainkey(self):
        """Turns out really long domain keys were having problems being parsed"""
        d = DKIM()

        domain = "foo.com"

        d.bits = 1024
        d.add_domain(domain, gen_key=True)
        dk = d.domainkey(domain)
        self.assertEqual(218, len(dk.p))

        d.bits = 2048
        d.add_domain(domain, gen_key=True)
        dk = d.domainkey(domain)
        self.assertEqual(394, len(dk.p))
        #pout.v(dk.p, dk.txt_f.contents())

        d.bits = 4096
        d.add_domain(domain, gen_key=True)
        dk = d.domainkey(domain)
        self.assertEqual(738, len(dk.p))

        d.bits = 8192
        d.add_domain(domain, gen_key=True)
        dk = d.domainkey(domain)
        self.assertEqual(1418, len(dk.p))

