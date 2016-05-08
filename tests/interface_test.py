import os

import testdata

from . import TestCase
#from stockton.dns import Domain
#from stockton.path import Filepath, Dirpath
#from stockton.interface.dkim import DKIM
from stockton.interface import SMTP, Postfix, PostfixCert, DKIM, Spam


class PostfixTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super(PostfixTest, cls).setUpClass()
        p = Postfix()
        p.install()

    def test_reset(self):
        p = Postfix()
        p.install()

        p.reset()
        self.assertFalse(p.master_f.exists())
        self.assertFalse(p.main_f.exists())
        self.assertFalse(p.helo_f.exists())
        self.assertEqual(0, p.virtual_d.count())

    def test_uninstall(self):
        p = Postfix()
        p.install()

        p.uninstall()
        self.assertFalse(p.conf_d)
        self.assertFalse(p.is_running())


class DKIMTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super(DKIMTest, cls).setUpClass()
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

