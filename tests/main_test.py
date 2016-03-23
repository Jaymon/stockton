from unittest import TestCase
import os
import re

import testdata
from captain.client import Captain

from stockton import cli
from stockton.path import Filepath, Dirpath
from stockton.concur.formats.postfix import Main, SMTPd, Master


class Stockton(Captain):
    def __init__(self, subcommand):
        self.cmd_prefix = "python -m stockton --verbose {}".format(subcommand.replace("_", "-"))
        super(Stockton, self).__init__("")

    def run(self, arg_str='', **process_kwargs):
        lines = ""
        for line in super(Stockton, self).run(arg_str, **process_kwargs):
            self.flush(line)
            lines += line
        return lines


def setUpModule():
    if os.environ["USER"] != "root":
        raise RuntimeError("User is not root, re-run this test with sudo")


class PrepareTest(TestCase):
    def setUp(self):
        cli.purge("postfix")

    def test_run(self):
        d = Dirpath("etc", "postfix")
        self.assertFalse(d.exists())

        s = Stockton("prepare")
        r = s.run("")

        # we use a file to get around filecache at os level
        f = Filepath(Main.dest_path)
        self.assertTrue(f.exists())


class ConfigureTest(TestCase):
    def setUp(self):
        f = Filepath(Main.dest_path)
        self.assertTrue(f.exists())

    def test_recv(self):
        s = Stockton("configure-recv")

        with self.assertRaises(RuntimeError):
            r = s.run("example.com --mailserver=mail.example.com")

        arg_str = "example.com --mailserver=mail.example.com --proxy-email=final@destination.com"
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
        s = Stockton("configure-recv")
        r = s.run(arg_str)
        f = Filepath(Main.dest_path)
        self.assertFalse(f.contains("foobar"))

        cli.running("postfix")

    def test_send(self):

        cli.purge("sasl2-bin", "libsasl2-modules")

        cli.package("cyrus-clients-2.4") # for smtptest

        s = Stockton("configure-send")
        arg_str = "example.com --mailserver=mail.example.com --smtp-password=1234 --state=CA --city=\"San Francisco\""
        r = s.run(arg_str)

        r = cli.run(
            "echo QUIT | smtptest -a smtp@example.com -w 1234 -t /etc/postfix/certs/mail.example.com.pem -p 587 localhost",
            capture_output=True
        )
        self.assertRegexpMatches(r, "235[^A]+Authentication\s+successful")

        r = cli.run(
            "echo QUIT | smtptest -a smtp@example.com -w 9876 -t /etc/postfix/certs/mail.example.com.pem -p 587 localhost",
            capture_output=True
        )
        self.assertRegexpMatches(r, "535[^E]+Error:\s+authentication\s+failed")

        r = cli.run(
            "echo QUIT | smtptest -a foo@example.com -w 1234 -t /etc/postfix/certs/mail.example.com.pem -p 587 localhost",
            capture_output=True
        )
        self.assertRegexpMatches(r, "535[^E]+Error:\s+authentication\s+failed")

#         r = cli.run(
#             "echo QUIT | smtptest -a smtp -w 1234 -t /etc/postfix/certs/example.com.pem -p 587 localhost",
#             capture_output=True
#         )
#         self.assertRegexpMatches(r, "535[^E]+Error:\s+authentication\s+failed")

        cli.running("postfix")

    def test_dkim(self):
        #self.test_recv() # we need a configured for receive postfix
        s = Stockton("configure-recv")
        r = s.run("example.com --mailserver=mail.example.com --proxy-email=final@destination.com")


        cli.purge("opendkim", "opendkim-tools")
        opendkim_d = Dirpath("/etc/opendkim")
        opendkim_d.delete()

        s = Stockton("configure-dkim")
        r = s.run()

        self.assertTrue(opendkim_d.exists())

        keytable_f = Filepath(opendkim_d, "KeyTable")
        self.assertEqual(1, keytable_f.lc())

        signingtable_f = Filepath(opendkim_d, "SigningTable")
        self.assertEqual(1, signingtable_f.lc())

        trustedhosts_f = Filepath(opendkim_d, "TrustedHosts")
        self.assertTrue("*.example.com" in trustedhosts_f.lines())

        cli.running("postfix")
        cli.running("opendkim")

    def test_srs(self):
        s = Stockton("configure-srs")
        r = s.run("")

        cli.running("postsrsd")


class DomainTest(TestCase):
    def setUp(self):
        f = Filepath(Main.dest_path)
        self.assertTrue(f.exists())

    def test_delete_domain(self):
        s = Stockton("configure-recv")
        r = s.run("example.com --mailserver=mail.example.com --proxy-email=final@dest.com")
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
        s = Stockton("configure-recv")
        r = s.run("--mailserver=mail.example.com")
        s = Stockton("configure-send")
        arg_str = "example.com --mailserver=mail.example.com --smtp-password=1234 --state=CA --city=\"San Francisco\""
        r = s.run(arg_str)

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

    def test_add_domain_proxy_file(self):
        s = Stockton("configure-recv")
        r = s.run("--mailserver=mail.example.com")

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
            s = Stockton("add-domain")
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
        s = Stockton("configure-recv")
        r = s.run("--mailserver=mail.example.com")
        s = Stockton("configure-send")
        arg_str = "example.com --mailserver=mail.example.com --smtp-password=1234 --state=CA --city=\"San Francisco\""
        r = s.run(arg_str)

        s = Stockton("add-domain")
        r = s.run("one.com --proxy-email=one@dest.com --smtp-password=1234")

        cli.package("cyrus-clients-2.4") # for smtptest
        r = cli.run(
            "echo QUIT | smtptest -a smtp@one.com -w 1234 -t /etc/postfix/certs/mail.example.com.pem -p 587 localhost",
            capture_output=True
        )
        self.assertRegexpMatches(r, "235[^A]+Authentication\s+successful")


class LockdownTest(TestCase):
    def setUp(self):
        cli.running("postfix")

    def test_run(self):
        s = Stockton("configure-recv")
        r = s.run("example.com --mailserver=mail.example.com --proxy-email=final@dest.com")

        s = Stockton("lockdown")
        r = s.run("--mailserver=mail.example.com")
        cli.running("postfix")

        helo_f = Filepath("/etc/postfix/helo.regexp")
        self.assertTrue(helo_f.exists())

