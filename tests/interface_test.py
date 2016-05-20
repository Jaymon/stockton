import os
import time

import testdata

from . import TestCase as BaseTestCase
#from stockton.dns import Domain
#from stockton.path import Filepath, Dirpath
#from stockton.interface.dkim import DKIM
from stockton.interface import Postfix, DKIM, SRS, Spam
from stockton.path import Filepath, Dirpath


class TestCase(BaseTestCase):
    service_class = None

    @classmethod
    def create_instance(cls):
        return cls.service_class()

    @classmethod
    def setup_env(cls):
        s = cls.create_instance()
        s.install()

    def test_lifecycle(self):
        s = self.create_instance()
        s.start()
        self.assertTrue(s.is_running())

        s.stop()
        self.assertFalse(s.is_running())

        s.restart()
        self.assertTrue(s.is_running())


class PostfixTest(TestCase):
    service_class = Postfix

    def test_uninstall(self):
        p = Postfix()
        p.uninstall()
        self.assertFalse(p.config_d.exists())
        self.assertFalse(p.is_running())

    def test_stray_output_files(self):
        """make sure the typescript problem is no longer a problem"""
        # https://github.com/Jaymon/stockton/issues/26
        f = Filepath(os.getcwd(), "typescript")

        f.delete()
        self.assertFalse(f.exists())

        p = Postfix()
        self.assertTrue(p.is_running())

        self.assertFalse(f.exists())


class DKIMTest(TestCase):
    service_class = DKIM

    def test_uninstall(self):
        d = DKIM()
        d.uninstall()
        self.assertFalse(d.config_f.exists())
        self.assertFalse(d.config_d.exists())

    def test_txt_info(self):
        d = DKIM()
        d.bits = 8192
        domain = "txtinfo.com"
        d.add_domain(domain, gen_key=True)

        dk = d.domainkey(domain)
        self.assertEqual(d.bits, dk.bits)
        self.assertNotEqual(None, dk.v)
        self.assertNotEqual(None, dk.k)
        self.assertNotEqual(None, dk.p)

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


class SRSTest(TestCase):
    service_class = SRS


class SpamTest(TestCase):
    service_class = Spam

    def test_lifecycle(self):
        sp = Spam()
        c = sp.config()
        c.update(
            ("ENABLED", 1),
        )
        c.save()
        sp.start()

        super(SpamTest, self).test_lifecycle()

    def test_uninstall(self):
        sp = Spam()
        sp.uninstall()
        self.assertFalse(sp.is_running())
        self.assertFalse(sp.home_d.exists())


del TestCase
