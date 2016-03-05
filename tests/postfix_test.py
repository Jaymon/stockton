from unittest import TestCase
import os

import testdata
from captain.client import Captain

from stockton import cli
from stockton.path import Filepath, Dirpath
from stockton.concur.formats.postfix import Main, SMTPd, Master


class Stockton(Captain):
    def __init__(self, subcommand):
        self.cmd_prefix = "python -m stockton {}".format(subcommand)
        super(Stockton, self).__init__("")

    def run(self, arg_str='', **process_kwargs):
#         pwd = os.path.dirname(__file__)
#         cmd_env = os.environ.copy()
#         cmd_env['PYTHONPATH'] = pwd + os.pathsep + cmd_env.get('PYTHONPATH', '')
#         c = Captain(self.path, cwd=self.cwd)
        lines = ""
        for line in super(Stockton, self).run(arg_str, **process_kwargs):
            self.flush(line)
            lines += line
        return lines


def setUpModule():
    if os.environ["USER"] != "root":
        raise RuntimeError("User is not root, re-run this test with sudo")


def tearDownModule():
    pass


def remove_postfix():
    cli.run("apt-get purge -y postfix")


class InstallTest(TestCase):
    def setUp(self):
        remove_postfix()

    def test_run(self):
        d = Dirpath("etc", "postfix")
        self.assertFalse(d.exists())

        s = Stockton("install")
        r = s.run("")

        # we use a file to get around filecache at os level
        f = Filepath(Main.dest_path)
        self.assertTrue(f.exists())


class ConfigureTest(TestCase):
    def setUp(self):
        f = Filepath(Main.dest_path)
        self.assertTrue(f.exists())

    def test_recv(self):
        s = Stockton("configure_recv")

        with self.assertRaises(RuntimeError):
            r = s.run("--domain=example.com --mailserver=mail.example.com")

        arg_str = "--domain=example.com --mailserver=mail.example.com --proxy-email=final@destination.com"
        r = s.run(arg_str)

        # make some changes to main
        m = Main(prototype_path=Main.dest_path)
        m.update(
            ("foobar", "1234")
        )
        m.save()

        f = Filepath(Main.dest_path)
        self.assertTrue(f.contains("foobar"))

        # re-run
        s = Stockton("configure_recv")
        r = s.run(arg_str)
        f = Filepath(Main.dest_path)
        self.assertFalse(f.contains("foobar"))

    def test_send(self):

        cli.purge("sasl2-bin", "libsasl2-modules")

        cli.package("cyrus-clients-2.4") # for smtptest

        s = Stockton("configure_send")
        arg_str = "--domain=example.com --mailserver=mail.example.com --smtp-password=1234 --state=CA --city=\"San Francisco\""
        r = s.run(arg_str)

        r = cli.run(
            "echo QUIT | smtptest -a smtp@mail.example.com -w 1234 -t /etc/postfix/certs/example.com.pem -p 587 localhost",
            capture_output=True
        )
        self.assertRegexpMatches(r, "235[^A]+Authentication\s+successful")

        r = cli.run(
            "echo QUIT | smtptest -a smtp@mail.example.com -w 9876 -t /etc/postfix/certs/example.com.pem -p 587 localhost",
            capture_output=True
        )
        self.assertRegexpMatches(r, "535[^E]+Error:\s+authentication\s+failed")

        r = cli.run(
            "echo QUIT | smtptest -a foo@mail.example.com -w 1234 -t /etc/postfix/certs/example.com.pem -p 587 localhost",
            capture_output=True
        )
        self.assertRegexpMatches(r, "535[^E]+Error:\s+authentication\s+failed")

#         r = cli.run(
#             "echo QUIT | smtptest -a smtp -w 1234 -t /etc/postfix/certs/example.com.pem -p 587 localhost",
#             capture_output=True
#         )
#         self.assertRegexpMatches(r, "535[^E]+Error:\s+authentication\s+failed")

    def test_dkim(self):
        #self.test_recv() # we need a configured for receive postfix
        s = Stockton("configure_recv")
        r = s.run("--domain=example.com --mailserver=mail.example.com --proxy-email=final@destination.com")


        cli.purge("opendkim", "opendkim-tools")
        opendkim_d = Dirpath("/etc/opendkim")
        opendkim_d.delete()

        s = Stockton("configure_dkim")
        r = s.run()

        self.assertTrue(opendkim_d.exists())

        keytable_f = Filepath(opendkim_d, "KeyTable")
        self.assertEqual(1, keytable_f.lc())

        signingtable_f = Filepath(opendkim_d, "SigningTable")
        self.assertEqual(1, signingtable_f.lc())

        trustedhosts_f = Filepath(opendkim_d, "TrustedHosts")
        self.assertTrue("*.example.com" in trustedhosts_f.lines())


class DomainTest(TestCase):
    def setUp(self):
        f = Filepath(Main.dest_path)
        self.assertTrue(f.exists())

    def test_add_domain_proxy_domains(self):
        s = Stockton("configure_recv")
        r = s.run("--domain=example.com --mailserver=mail.example.com --proxy-email=final@dest.com")

        proxy_domains = testdata.create_dir()
        f = testdata.create_files({
            "foo.com": "\n".join([
                "one@foo.com                foo@dest.com",
                "two@foo.com                foo@dest.com",
                "three@foo.com              foo@dest.com",
            ]),
            "bar.com": "\n".join([
                "one@bar.com                bar@dest.com",
                "two@bar.com                bar@dest.com",
                "three@bar.com              bar@dest.com",
            ]),
        }, proxy_domains)

        s = Stockton("add_domain")
        r = s.run("--proxy-domains={}".format(proxy_domains))


    def test_add_domain_domain(self):
        """pass in the domain and the proxy"""
        s = Stockton("configure_recv")
        r = s.run("--domain=example.com --mailserver=mail.example.com --proxy-email=final@dest.com")

        s = Stockton("add_domain")
        onef = Filepath("/etc/postfix/virtual/addresses/one.com")
        twof = Filepath("/etc/postfix/virtual/addresses/two.com")
        df = Filepath("/etc/postfix/virtual/domains")

        r = s.run("--domain=one.com --proxy-email=one@dest.com")
        self.assertTrue(onef.contains("^@one.com"))
        self.assertTrue(df.contains("one.com"))

        r = s.run("--domain=two.com --proxy-email=two@dest.com")
        self.assertTrue(onef.contains("^@one.com"))
        self.assertTrue(df.contains("one.com"))
        self.assertTrue(twof.contains("two@dest.com"))
        self.assertTrue(df.contains("two.com"))

        return

        virtual_d = Dirpath("/etc/postfix/virtual")






        return


        s = Stockton("add_domain")
        opendkim_d = Dirpath("/etc/opendkim")
        virtual_d = Dirpath("/etc/postfix/virtual")

        domains_f = Filepath(virtual_d, "domains")
        #domains_lc = domains_f.lc()

        keytable_f = Filepath(opendkim_d, "KeyTable")
        #keytable_lc = keytable_f.lc()

        signingtable_f = Filepath(opendkim_d, "SigningTable")
        #signingtable_lc = signingtable_f.lc()

        trustedhosts_f = Filepath(opendkim_d, "TrustedHosts")

        r = s.run("--domain=foo.com --proxy-email=foo@final.com")
        pout.v(keytable_f.contents())
        self.assertEqual(1, keytable_f.lc())
        self.assertEqual(1, signingtable_f.lc())
        pout.v(domains_f.contents())
        self.assertEqual(1, domains_f.lc())
        self.assertTrue("*.foo.com" in trustedhosts_f.lines())

        r = s.run("--domain=bar.com --proxy-email=foo@final.com")
        self.assertEqual(2, keytable_f.lc())
        self.assertEqual(2, signingtable_f.lc())
        self.assertEqual(2, domains_f.lc())
        self.assertTrue("*.bar.com" in trustedhosts_f.lines())





