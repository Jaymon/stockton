import os
import re

import testdata

from stockton import cli
from stockton.path import Filepath, Dirpath
from stockton.concur.formats.postfix import Main, SMTPd, Master
from stockton.interface import Postfix, Spam, DKIM, SRS, SMTP

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

        sr = SRS()
        self.assertTrue(sr.is_running())


class DomainTest(TestCase):
#     @classmethod
#     def setup_env(cls):
#         dk = DKIM()
#         dk.uninstall()
#         super(DomainTest, cls).setup_env()

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

        # to make sure this works completely, we completely remove postfix
        p = Postfix()
        p.reset()

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
        s = Stockton("configure-dkim")
        r = s.run()

        p = Postfix()
        dk = DKIM()

        s = Stockton("add-domain")
        one_f = p.address("one.com")
        two_f = p.address("two.com")
        domains_f = p.domains_f

        r = s.run("one.com --proxy-email=one@dest.com")
        self.assertTrue(one_f.contains("^@one.com"))
        self.assertTrue(domains_f.contains("one.com"))

        r = s.run("two.com --proxy-email=two@dest.com")
        self.assertTrue(one_f.contains("^@one.com"))
        self.assertTrue(domains_f.contains("one.com"))
        self.assertTrue(two_f.contains("two@dest.com"))
        self.assertTrue(domains_f.contains("two.com"))

        opendkim_d = dk.config_d
        keytable_f = dk.keytable_f
        signingtable_f = dk.signingtable_f
        trustedhosts_f = dk.trustedhosts_f

        self.assertTrue(keytable_f.contains("one.com"))
        self.assertTrue(signingtable_f.contains("one.com"))
        self.assertTrue(keytable_f.contains("two.com"))
        self.assertTrue(signingtable_f.contains("two.com"))
        self.assertTrue("*.one.com" in trustedhosts_f.lines())
        self.assertTrue("*.two.com" in trustedhosts_f.lines())

    def test_add_domain_smtp(self):
        s = Stockton("configure-send")
        r = s.run("--mailserver=mail.example.com")

        s = Stockton("add-domain")
        r = s.run("one.com --proxy-email=one@dest.com --smtp-password=1234")

        cli.package("cyrus-clients-2.4") # for smtptest
        r = cli.run(
            "echo QUIT | smtptest -a smtp@one.com -w 1234 -t /etc/postfix/certs/mail.example.com.pem -p 587 localhost"
        )
        self.assertRegexpMatches(r, "235[^A]+Authentication\s+successful")

        r = cli.run(
            "echo QUIT | smtptest -a smtp@one.com -w 9876 -t /etc/postfix/certs/mail.example.com.pem -p 587 localhost"
        )
        self.assertRegexpMatches(r, "535[^E]+Error:\s+authentication\s+failed")

        r = cli.run(
            "echo QUIT | smtptest -a foo@one.com -w 1234 -t /etc/postfix/certs/mail.example.com.pem -p 587 localhost"
        )
        self.assertRegexpMatches(r, "535[^E]+Error:\s+authentication\s+failed")




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
    def test_all(self):
        s = Stockton("lockdown")
        r = s.run("--mailserver=mail.example.com")

        p = Postfix()
        sp = Spam()
        self.assertTrue(p.is_running())
        self.assertTrue(p.helo_f.exists())
        self.assertTrue(sp.is_running())

    def test_spam(self):
        s = Stockton("lockdown-spam")
        r = s.run()

        sp = Spam()
        self.assertTrue(sp.is_running())

    def test_postfix(self):
        self.setup_domain("example.com")

        s = Stockton("lockdown-postfix")
        r = s.run("--mailserver=mail.example.com")

        p = Postfix()
        self.assertTrue(p.is_running())
        self.assertTrue(p.helo_f.exists())


class InstallationTest(TestCase):
    @classmethod
    def setup_env(cls):
        #super(ConfigureDKIMTest, cls).setup_env()
        pass

    def test_idempotence(self):
        self.test_uninstall()
        self.test_install()

        p = Postfix()
        dk = DKIM()
        sp = Spam()
        sm = SMTP()

        main_hash = p.main_f.checksum
        master_hash = p.master_f.checksum
        dk_hash = dk.config_f.checksum
        sp_config_hash = sp.config_f.checksum
        sp_local_hash = sp.local_f.checksum
        sm_config_hash = sm.config_f.checksum

        self.test_install()

        # just to make sure there is no caching issues
        p = Postfix()
        dk = DKIM()
        sp = Spam()
        sm = SMTP()

        self.assertEqual(main_hash, p.main_f.checksum)
        self.assertEqual(master_hash, p.master_f.checksum)
        self.assertEqual(dk_hash, dk.config_f.checksum)
        self.assertEqual(sp_config_hash, sp.config_f.checksum)
        self.assertEqual(sp_local_hash, sp.local_f.checksum)
        self.assertEqual(sm_config_hash, sm.config_f.checksum)

    def test_uninstall(self):
        s = Stockton("uninstall")
        r = s.run()

        p = Postfix()
        self.assertFalse(p.is_running())
        self.assertFalse(p.exists())

        dk = DKIM()
        self.assertFalse(dk.is_running())
        self.assertFalse(dk.exists())

        sr = SRS()
        self.assertFalse(sr.is_running())

        sp = Spam()
        self.assertFalse(sp.is_running())
        self.assertFalse(sp.exists())

        sm = SMTP()
        self.assertFalse(sm.exists())

    def test_install_proxy_domains(self):
        s = Stockton("install")
        proxy_domains = testdata.create_files({
            "pd1.com.txt": [
                "one@pd1.com                foo@dest.com",
                "",
            ],
            "pd2.com": [
                "one@pd2.com                bar@dest.com",
                "",
            ],
        })

        r = s.run("--mailserver={} --proxy-domains={} --smtp-password=1234".format(
            "mail.example.com",
            proxy_domains
        ))
        # if there was no error than yay, it worked

    def test_install(self):
        s = Stockton("install")
        arg_str = " ".join([
            "--mailserver=mail.example.com",
            "--smtp-password=1234",
            "--proxy-email=d@dest.com",
            "front.com"
        ])
        r = s.run(arg_str)

        p = Postfix()
        self.assertTrue(p.is_running())

        dk = DKIM()
        self.assertTrue(dk.is_running())

        sr = SRS()
        self.assertTrue(sr.is_running())

        sp = Spam()
        self.assertTrue(sp.is_running())

