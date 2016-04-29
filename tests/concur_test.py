from unittest import TestCase

import testdata

from stockton.concur.formats.base import ConfigFile, Config, ConfigSection
from stockton.concur.formats import postfix
from stockton.concur.formats import generic


def setUpModule():
    pass


def tearDownModule():
    pass


# class ConfigFileTest(TestCase):
#     def test_replay(self):
#         path = testdata.create_file("counting", "\n".join([str(x) for x in range(5)]))
# 
#         class RConSec(ConfigSection):
#             def _parse(self, fp):
#                 self.name = fp.line
# 
#         class RCon(Config):
#             parse_class = RConSec
# 
# 
#         fp = ConfigFile(path, RCon())
# 
#         c = fp.next()
#         self.assertEqual(0, int(c.line))
# 
#         c = fp.next()
#         self.assertEqual(1, int(c.line))
# 
#         fp.replay(c, fp.line, fp.line_number)
#         c = fp.next()
#         self.assertEqual(1, int(c.line))
# 
#         c = fp.next()
#         self.assertEqual(2, int(c.line))
# 
#         c = fp.next()
#         self.assertEqual(3, int(c.line))
# 
#         fp.replay(c, fp.line, fp.line_number)
#         c = fp.next()
#         self.assertEqual(3, int(c.line))
# 
#         c = fp.next()
#         self.assertEqual(4, int(c.line))
# 
#         with self.assertRaises(StopIteration):
#             fp.next()


class SpaceTest(TestCase):
    def test__parse(self):
        path = testdata.create_file("space.conf", "\n".join([
            "# Log to syslog",
            "Syslog			yes",
            "# Required to use local socket with MTAs that access the socket as a non-",
            "# privileged user (e.g. Postfix)",
            "UMask			002",
            "",
            "# Sign for example.com with key in /etc/mail/dkim.key using",
            "# selector '2007' (e.g. 2007._domainkey.example.com)",
            "#Domain			example.com",
        ]))

        c = generic.SpaceConfig(prototype_path=path)
        self.assertTrue(c["syslog"])
        self.assertTrue(c["UMask"])
        self.assertTrue(c["Domain"])
        #self.assertEqual(3, len(c.options))


class PostfixTest(TestCase):
    def test_main_update(self):
        contents = "\n".join([
            "foo = bar",
            "che = baz",
        ])
        path = testdata.create_file("main.cf", contents)
        c = postfix.Main(dest_path=path, prototype_path=path)

        c.update(
            ("foo", "rab")
        )
        c.save()

        c2 = postfix.Main(dest_path=path, prototype_path=path)
        self.assertEqual("rab", c2["foo"].val)
        self.assertEqual("baz", c2["che"].val)

    def test_main_oneline(self):
        contents = "\n".join([
            "virtual_alias_map = hash:/some/path/one",
            "foo = bar",
            "che = baz",
        ])
        path = testdata.create_file("main.cf", contents)
        c = postfix.Main(prototype_path=path)
        self.assertEqual(contents, str(c))

    def test_main_multiline(self):
        contents = "\n".join([
            "virtual_alias_map = hash:/some/path/one,",
            "  hash:/some/path/two,",
            "  hash:/some/path/three",
        ])
        path = testdata.create_file("main.cf", contents)
        c = postfix.Main(prototype_path=path)
        self.assertEqual(contents, str(c))

        contents = "\n".join([
            "virtual_alias_map = hash:/some/path/one,",
            "  hash:/some/path/two,",
            "  hash:/some/path/three",
            "virtual_alias_domains = /another/path/and/stuff",
        ])
        path = testdata.create_file("main.cf", contents)
        c = postfix.Main(prototype_path=path)
        self.assertEqual(contents, str(c))

        c["virtual_alias_map"] = c["virtual_alias_map"].val + "\n  hash:/some/path/four"
        contents = "\n".join([
            "virtual_alias_map = hash:/some/path/one,",
            "  hash:/some/path/two,",
            "  hash:/some/path/three",
            "  hash:/some/path/four",
            "virtual_alias_domains = /another/path/and/stuff",
        ])
        self.assertEqual(contents, str(c))

    def test_master_multiple_same_name(self):
        contents = "\n".join([
            "smtp      inet  n       -       -       -       -       smtpd",
            "#smtp      inet  n       -       -       -       1       postscreen",
            "smtp      unix  -       -       -       -       -       smtp",
        ])
        master_path = testdata.create_file("master.cf", contents)

        master = postfix.Master(prototype_path=master_path)
        for smtp in master["smtp"]:
            smtp.chroot = "n"

        contents = "\n".join([
            "smtp      inet  n       -       n       -       -       smtpd",
            "smtp      inet  n       -       n       -       1       postscreen",
            "smtp      unix  -       -       n       -       -       smtp",
        ])
        self.assertEqual(contents, str(master))

    def test_master_option(self):
        master = postfix.Master()
        class FP(object):
            line = "  -o foo=yes"

        mo = master.create_option()
        mo.parse(FP())
        self.assertEqual("foo", mo.name)
        self.assertEqual("yes", mo.val)

        mo.val = "no"
        self.assertEqual("no", mo.val)
        self.assertEqual("  -o foo=no", str(mo))


    def test_master_section_manipulate_option(self):
        master_path = testdata.create_file("master.cf", "\n".join([
            "smtp      inet  n       -       -       -       -       smtpd",
            "  -o foo=yes",
            "  -o bar=yes",
        ]))

        master = postfix.Master(prototype_path=master_path)
        self.assertTrue(isinstance(master["smtp"], postfix.MasterSection))

        contents = "\n".join([
            "smtp      inet  n       -       -       -       -       smtpd",
            "  -o foo=no",
            "  -o bar=yes",
        ])
        master["smtp"]["foo"] = "no"
        self.assertEqual(contents, str(master))

    def test_master_section_append_option(self):
        master_path = testdata.create_file("master.cf", "\n".join([
            "smtp inet n - - - - smtpd",
            "  -o foo=yes",
        ]))

        master = postfix.Master(prototype_path=master_path)
        contents = "\n".join([
            "smtp inet n - - - - smtpd",
            "  -o foo=yes",
            "  -o bar=yes",
        ])
        master["smtp"]["bar"] = "yes"
        self.assertEqual(contents, str(master))

    def test_master_sections(self):
        contents = "\n".join([
            "one inet n - - - - smtpd",
            "  -o smtpd_tls_wrappermode=yes",
            "two inet n - - - - qmqpd",
            "three fifo n - - 60 1 pickup",
        ])
        master_path = testdata.create_file("master.cf", contents)

        master = postfix.Master(prototype_path=master_path)
        self.assertEqual(contents, str(master))

    def test_master_section_commented(self):
        contents = "#smtps     inet  n       -       -       -       -       smtpd"
        master_path = testdata.create_file("master.cf", contents)

        master = postfix.Master(prototype_path=master_path)
        master["smtps"].modified = True
        self.assertEqual("smtps     inet  n       -       -       -       -       smtpd", str(master))

    def test_master_comments(self):
        master_path = testdata.create_file("master.cf", "\n".join([
            "#",
            "# this is the stuff before the first section",
            "#",
            "# ==========================================================================",
            "# service type  private unpriv  chroot  wakeup  maxproc command + args",
            "#               (yes)   (yes)   (yes)   (never) (100)",
            "# ==========================================================================",
            "smtp      inet  n       -       -       -       -       smtpd",
            "  -o smtpd_tls_wrappermode=yes",
            "  -o smtpd_sasl_auth_enable=yes",
            "  -o smtpd_client_restrictions=permit_sasl_authenticated,reject",
            "  -o milter_macro_daemon_name=ORIGINATING",
        ]))

        master = postfix.Master(prototype_path=master_path)
        self.assertEqual(8, len(master.lines))
        self.assertEqual(4, len(master["smtp"].lines))

    def test_master_section_modify_option(self):
        master_path = testdata.create_file("master.cf", "\n".join([
            "#submission inet n       -       -       -       -       smtpd",
            "#  -o syslog_name=postfix/submission",
            "#  -o smtpd_tls_security_level=encrypt",
            "#  -o smtpd_sasl_auth_enable=yes",
            "#  -o smtpd_reject_unlisted_recipient=no",
            "#  -o smtpd_client_restrictions=one",
            "#  -o smtpd_helo_restrictions=two",
            "#  -o smtpd_sender_restrictions=three",
            "#  -o smtpd_recipient_restrictions=",
            "#  -o smtpd_relay_restrictions=permit_sasl_authenticated,reject",
            "#  -o milter_macro_daemon_name=ORIGINATING"
        ]))

        m = postfix.Master(prototype_path=master_path)
        m["submission"].modified = True
        m["submission"].update(
            ("syslog_name", "postfix/submission"),
            ("smtpd_tls_security_level", "may"),
            ("smtpd_tls_cert_file", "/foo/bar.pem"),
            ("smtpd_sasl_auth_enable", "yes"),
            ("smtpd_reject_unlisted_recipient", "no"),
            ("smtpd_relay_restrictions", "permit_sasl_authenticated,reject"),
            ("milter_macro_daemon_name", "ORIGINATING")
        )
        self.assertEqual(4, str(m).count("#"))
        self.assertEqual(11, len(m["submission"].options))

    def test_master_add_section(self):
#         master_path = testdata.create_file("master.cf", "\n".join([
#             "smtp      inet  n       -       -       -       -       smtpd",
#         ]))
        master = postfix.Master(prototype_path="")
        section = master.create_section("smtp inet n - - - - smtpd")
        self.assertEqual(0, len(master.sections))
        master["smtp"] = section
        self.assertEqual(1, len(master.sections))
        self.assertEqual("smtp", master["smtp"].name)



class ConfigTest(TestCase):
    def test_update_before(self):
        contents = "\n".join([
            "foo = 1",
            "baz = 3",
        ])
        path = testdata.create_file("update_before.conf", contents)
        conf = Config(prototype_path=path)

        conf.update_before("baz", ("bar", 2))
        self.assertTrue("foo" in str(conf.lines[0]))
        self.assertTrue("bar" in str(conf.lines[1]))
        self.assertTrue("baz" in str(conf.lines[2]))

    def test_options(self):
        contents = "\n".join([
            "foo=bar",
            "baz = che",
        ])
        path = testdata.create_file("main.cf", contents)

        conf = Config(prototype_path=path)
        self.assertEqual(contents, str(conf))

        contents = "\n".join([
            "foo=bar",
            "baz = che",
        ])
        conf["foo"] = "che"
        conf["baz"] = "bar"

        contents = "\n".join([
            "foo = che",
            "baz = bar",
        ])
        self.assertEqual(contents, str(conf))

