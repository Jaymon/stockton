import os
import re

import testdata

from stockton import cli
from stockton.path import Filepath, Dirpath
from stockton.concur.formats.postfix import Main, SMTPd, Master
from stockton.interface import Postfix, Spam, DKIM

from . import TestCase as BaseTestCase, Stockton


class TestCase(BaseTestCase):
#     def setUp(self):
#         super(TestCase, self).setUp()

    @classmethod
    def setup_env(cls):
        p = Postfix()
        if not p.main_f.exists():
            s = Stockton("prepare")
            r = s.run()

    def setup_domain(self, domain):
        s = Stockton("configure-recv")
        r = s.run("--mailserver=mail.example.com")

        s = Stockton("add-domain")
        r = s.run("{} --proxy-email=dest@dest.com".format(domain))


class PrepareTest(TestCase):
    @classmethod
    def setup_env(cls):
        cli.purge("postfix")

    def test_run(self):
        p = Postfix()
        d = p.config_d
        self.assertFalse(d.exists())

        s = Stockton("prepare")
        r = s.run()

        f = p.main_f
        self.assertTrue(f.exists())


class ConfigureRecvTest(TestCase):
    @classmethod
    def setup_env(cls):
        super(ConfigureRecvTest, cls).setup_env()

        s = Stockton("configure-recv")
        r = s.run("--mailserver=mail.example.com")

    def test_recv(self):
        p = Postfix()

        # make some changes to main
        m = p.main()
        m.update(
            ("myhostname", "foobar.com")
        )
        m.save()

        f = p.main_f
        self.assertTrue(f.contains("foobar.com"))

        # re-run
        s = Stockton("configure-recv")
        r = s.run("--mailserver=mail.example.com")
        f = p.main_f
        self.assertFalse(f.contains("foobar.com"))
        self.assertTrue(p.is_running())


class ConfigureSendTest(TestCase):
    def test_send(self):
        p = Postfix()
        s = Stockton("configure-send")
        r = s.run("--mailserver=mail.example.com")
        self.assertTrue(p.is_running())


class ConfigureDKIMTest(TestCase):
    @classmethod
    def setup_env(cls):
        dk = DKIM()
        dk.uninstall()
        super(ConfigureDKIMTest, cls).setup_env()

    def test_dkim(self):
        #self.test_recv() # we need a configured for receive postfix
        self.setup_domain("example.com")

        s = Stockton("configure-dkim")
        r = s.run()

        dk = DKIM()
        p = Postfix()
        self.assertTrue(dk.config_d.exists())
        self.assertEqual(1, dk.keytable_f.lc())
        self.assertEqual(1, dk.signingtable_f.lc())
        self.assertTrue("*.example.com" in dk.trustedhosts_f.lines())
        self.assertTrue(dk.is_running())
        self.assertTrue(p.is_running())


class ConfigureSRSTest(TestCase):
    def test_srs(self):
        s = Stockton("configure-srs")
        r = s.run("")

        cli.running("postsrsd")


class DomainTest(TestCase):
    def test_delete_domain(self):
        self.setup_domain("example.com")
        s = Stockton("configure_dkim")
        r = s.run()

        s = Stockton("add-domain")
        r = s.run("todelete.com --proxy-email=todelete@dest.com")

        s = Stockton("delete-domain")
        r = s.run("todelete.com")

        # verify
        af = Filepath("/etc/postfix/virtual/addresses/todelete.com")
        self.assertFalse(af.exists())

        df = Filepath("/etc/postfix/virtual/domains")
        self.assertFalse(df.contains("todelete.com"))

        opendkim_d = Dirpath("/etc/opendkim")
        #keytable_f = Filepath(opendkim_d, "KeyTable")
        signingtable_f = Filepath(opendkim_d, "SigningTable")
        self.assertFalse(signingtable_f.contains("todelete.com"))

        trustedhosts_f = Filepath(opendkim_d, "TrustedHosts")
        self.assertFalse(trustedhosts_f.contains("todelete.com"))

    def test_add_domain_proxy_file_smtp(self):
        self.setup_domain("example.com")
        s = Stockton("configure-send")
        r = s.run("--mailserver=mail.example.com")

        proxy_addresses = testdata.create_file("foo.com", [
            "one@foo.com                foo@dest1.com",
            "two@foo.com                foo@dest2.com",
            "three@foo.com              foo@dest3.com",
            "",
        ])

        s = Stockton("add-domain")
        r = s.run("foo.com --proxy-file={} --smtp-password=12345".format(proxy_addresses))

        cli.package("cyrus-clients-2.4") # for smtptest
        r = cli.run(
            "echo QUIT | smtptest -a smtp@foo.com -w 12345 -t /etc/postfix/certs/mail.example.com.pem -p 587 localhost",
            capture_output=True
        )
        self.assertRegexpMatches(r, "235[^A]+Authentication\s+successful")

    def test_add_domain_proxy_file_no_smtp(self):
        s = Stockton("add-domain")
        proxy_domains = testdata.create_files({
            "foo.com": "\n".join([
                "one@foo.com                foo@dest.com",
                "two@foo.com                foo@dest.com",
                "three@foo.com              foo@dest.com",
                "",
            ]),
            "bar.com": "\n".join([
                "one@bar.com                bar@dest.com",
                "two@bar.com                bar@dest.com",
                "three@bar.com              bar@dest.com",
                "",
            ]),
        })

        for f in proxy_domains:
            r = s.run("{} --proxy-file={}".format(f.name, f))

        contents = "\n".join([
            "@foo.com                   foo@dest.com",
            "",
        ])
        f = testdata.create_file("foo.com", contents)

        r = s.run("{} --proxy-file={}".format(f.name, f))
        foo = Filepath("/etc/postfix/virtual/addresses/foo.com")
        self.assertEqual(contents, foo.contents())

        # Let's check structure because I was having a lot of problems with getting
        # the structure...

        # domains file should have 2 domains in it
        domains_f = Filepath("/etc/postfix/virtual/domains")
        self.assertEqual(2, domains_f.lc())
        self.assertTrue(domains_f.contains("^foo\.com$"))

        m = Main(prototype_path=Main.dest_path)
        # we can't guarrantee foo, bar order so we match one line at a time
        self.assertTrue(re.search("^hash:[/a-z]+?(bar|foo)\.com,", m["virtual_alias_maps"].val, re.M))
        self.assertTrue(re.search("^\s+hash:[/a-z]+?(bar|foo)\.com$", m["virtual_alias_maps"].val, re.M))

    def test_add_domains(self):
        s = Stockton("configure-recv")
        r = s.run("--mailserver=mail.example.com")

        s = Stockton("add-domains")

        # a file with different domains
        proxy_domains = testdata.create_files({
            "foo2.com.txt": [
                "one@foo3.com                foo@dest.com",
                "one@bar3.com                bar@dest.com",
                "",
            ],
        })
        with self.assertRaises(RuntimeError):
            r = s.run("--proxy-domains={}".format(proxy_domains))

        # 2 files with the same domain
        proxy_domains = testdata.create_files({
            "foo2.com.txt": [
                "one@foo2.com                foo@dest.com",
                "",
            ],
            "bar2.com": [
                "one@foo2.com                bar@dest.com",
                "",
            ],
        })
        with self.assertRaises(RuntimeError):
            r = s.run("--proxy-domains={}".format(proxy_domains))

        proxy_domains = testdata.create_files({
            "foo.com.txt": [
                "one@foo.com                foo@dest.com",
                "two@foo.com                foo@dest.com",
                "three@foo.com              foo@dest.com",
                "",
            ],
            "bar.com": [
                "one@bar.com                bar@dest.com",
                "two@bar.com                bar@dest.com",
                "three@bar.com              bar@dest.com",
                "",
            ],
            "che.org.txt": [
                "@che.org                   che@dest.com",
                "",
            ],
        })

        r = s.run("--proxy-domains={} --smtp-password=1234".format(proxy_domains))
        self.assertTrue("Adding domain foo.com" in r)
        self.assertTrue("Adding domain bar.com" in r)
        self.assertTrue("Adding domain che.org" in r)

    def test_add_domain_domain(self):
        """pass in the domain and the proxy"""
        s = Stockton("configure-recv")
        r = s.run("--mailserver=mail.example.com")
        s = Stockton("configure-dkim")
        r = s.run()

        s = Stockton("add-domain")
        onef = Filepath("/etc/postfix/virtual/addresses/one.com")
        twof = Filepath("/etc/postfix/virtual/addresses/two.com")
        df = Filepath("/etc/postfix/virtual/domains")

        r = s.run("one.com --proxy-email=one@dest.com")
        self.assertTrue(onef.contains("^@one.com"))
        self.assertTrue(df.contains("one.com"))

        r = s.run("two.com --proxy-email=two@dest.com")
        self.assertTrue(onef.contains("^@one.com"))
        self.assertTrue(df.contains("one.com"))
        self.assertTrue(twof.contains("two@dest.com"))
        self.assertTrue(df.contains("two.com"))

        opendkim_d = Dirpath("/etc/opendkim")
        keytable_f = Filepath(opendkim_d, "KeyTable")
        signingtable_f = Filepath(opendkim_d, "SigningTable")
        trustedhosts_f = Filepath(opendkim_d, "TrustedHosts")

        self.assertEqual(2, keytable_f.lc())
        self.assertEqual(2, signingtable_f.lc())
        #self.assertTrue("*.example.com" in trustedhosts_f.lines())
        self.assertTrue("*.one.com" in trustedhosts_f.lines())
        self.assertTrue("*.two.com" in trustedhosts_f.lines())

    def test_add_domain_smtp(self):
        self.setup_domain("example.com")
        s = Stockton("configure-send")
        arg_str = "example.com --mailserver=mail.example.com --smtp-password=1234"
        r = s.run(arg_str)

        s = Stockton("add-domain")
        r = s.run("one.com --proxy-email=one@dest.com --smtp-password=1234")

        cli.package("cyrus-clients-2.4") # for smtptest
        r = cli.run(
            "echo QUIT | smtptest -a smtp@one.com -w 1234 -t /etc/postfix/certs/mail.example.com.pem -p 587 localhost",
            capture_output=True
        )
        self.assertRegexpMatches(r, "235[^A]+Authentication\s+successful")

#         cli.package("cyrus-clients-2.4") # for smtptest
#
#         s = Stockton("configure-send")
#         arg_str = "example.com --mailserver=mail.example.com --smtp-password=1234"
#         r = s.run(arg_str)
# 
#         r = cli.run(
#             "echo QUIT | smtptest -a smtp@example.com -w 1234 -t /etc/postfix/certs/mail.example.com.pem -p 587 localhost",
#             capture_output=True
#         )
#         self.assertRegexpMatches(r, "235[^A]+Authentication\s+successful")
# 
#         r = cli.run(
#             "echo QUIT | smtptest -a smtp@example.com -w 9876 -t /etc/postfix/certs/mail.example.com.pem -p 587 localhost",
#             capture_output=True
#         )
#         self.assertRegexpMatches(r, "535[^E]+Error:\s+authentication\s+failed")
# 
#         r = cli.run(
#             "echo QUIT | smtptest -a foo@example.com -w 1234 -t /etc/postfix/certs/mail.example.com.pem -p 587 localhost",
#             capture_output=True
#         )
#         self.assertRegexpMatches(r, "535[^E]+Error:\s+authentication\s+failed")
# 
# #         r = cli.run(
# #             "echo QUIT | smtptest -a smtp -w 1234 -t /etc/postfix/certs/example.com.pem -p 587 localhost",
# #             capture_output=True
# #         )
# #         self.assertRegexpMatches(r, "535[^E]+Error:\s+authentication\s+failed")


class LockdownTest(TestCase):
    def test_spam(self):
        s = Stockton("lockdown-spam")
        r = s.run()
        #pout.v(r)

        sp = Spam()
        self.assertTrue(sp.is_running())

    def test_postfix(self):
        self.setup_domain("example.com")

        s = Stockton("lockdown-postfix")
        r = s.run("--mailserver=mail.example.com")

        p = Postfix()
        self.assertTrue(p.is_running())
        self.assertTrue(p.helo_f.exists())

