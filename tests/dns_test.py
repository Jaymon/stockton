from unittest import TestCase, SkipTest

import testdata

from stockton import dns
from stockton.dns import Domain
from stockton.path import Filepath, Dirpath


class DomainTest(TestCase):
    def test_mx(self):
        d = Domain("example.com")
        def monkey_query(self, *args, **kwargs):
            return "\n".join([
                "{} mail is handled by 10 mailstore1.secureserver.net.".format(d.host),
                "{} mail is handled by 0 smtp.secureserver.net.".format(d.host),
                "",
            ])
        testdata.patch(d, query=monkey_query)

        mxs = d.mx()
        self.assertEqual(2, len(mxs))

        mxs = d.mx("smtp.secureserver.net")
        self.assertEqual(1, len(mxs))

        vs = d.nameservers("000.00.000.000")
        self.assertEqual(0, len(vs))

    def test_nameservers(self):
        d = Domain("example.com")
        def monkey_query(self, *args, **kwargs):
            return "\n".join([
                "{} name server ns62.domaincontrol.com.".format(d.host),
                "{} name server ns61.domaincontrol.com.".format(d.host),
                ""
            ])
        testdata.patch(d, query=monkey_query)

        vs = d.nameservers()
        self.assertEqual(2, len(vs))

        vs = d.nameservers("ns62.domaincontrol.com")
        self.assertEqual(1, len(vs))

        vs = d.nameservers("000.00.000.000")
        self.assertEqual(0, len(vs))


    def test_a(self):
        d = Domain("example.com")
        def monkey_query(self, *args, **kwargs):
            return "\n".join([
                "{} has address 100.70.100.200".format(d.host),
                "{} has address 101.71.101.201".format(d.host),
                ""
            ])
        testdata.patch(d, query=monkey_query)

        vs = d.a()
        self.assertEqual(2, len(vs))

        vs = d.a("101.71.101.201")
        self.assertEqual(1, len(vs))

        vs = d.a("000.00.000.000")
        self.assertEqual(0, len(vs))

    def test_txt(self):
        d = Domain("example.com")
        def monkey_query(self, *args, **kwargs):
            return "\n".join([
                "{} descriptive text \"google-site-verification=dakfkdkaureurjkfdhiqerukSHA\"".format(d.host),
                "{} descriptive text \"v=spf1 include:_spf.google.com include:sendgrid.net include:spf.mandrillapp.com ~all\"".format(d.host),
                "{} descriptive text \"v=spf1 include:servers.mcsv.net ?all\"".format(d.host),
                ""
            ])
        testdata.patch(d, query=monkey_query)

        vs = d.txt()
        self.assertEqual(3, len(vs))

        vs = d.txt("spf")
        self.assertEqual(2, len(vs))

        vs = d.txt("000.00.000.000")
        self.assertEqual(0, len(vs))

    def test_ptr(self):
        d = Domain("123.456.789.100")
        def monkey_query(self, *args, **kwargs):
            return "\n".join([
                "203.68.131.104.in-addr.arpa domain name pointer {}.".format("example.com"),
                ""
            ])
        testdata.patch(d, query=monkey_query)

        vs = d.ptr()
        self.assertEqual(1, len(vs))

        vs = d.ptr("example.com")
        self.assertEqual(1, len(vs))

        vs = d.ptr("000.00.000.000")
        self.assertEqual(0, len(vs))

    def test_rdns(self):
        def monkey_query(self, *args, **kwargs):
            return "\n".join([
                "123.456.789.100.in-addr.arpa domain name pointer {}.".format(d.host),
                ""
            ])
        MonkeyDomain = testdata.patch(
            Domain,
            a=lambda *a, **kw: ["123.456.789.100"],
            query=monkey_query
        )

        d = MonkeyDomain("example.com")
        vs = d.rdns()
        self.assertEqual("123.456.789.100", vs[0])

#     def test_domainkey(self):
#         import sys
#         import os
#         sys.path.insert(0, os.curdir)
# 
#         monkey_text_valid = "".join([
#             'v=DKIM1; k=rsa; ',
#             'p=MIIBIjANBgkqhkiG9wcheQEFAAOCAQ8AMIIBCgKCAQEAy14JM1EVS+y5CsPo',
#             'xvokcnYKlHVownd7A8RqcW0Ndb/PMZy1htsLgskDLwVbwp4TjxaNi6Wxakt0Kz',
#             'xeLT6AC7vmg0zHyMUzy0ra6sWyg3lPfool6wHKlF0ary2KQmbd6yyN+AyiQIT6',
#             'kq+E7hqyElnuAWUjA/Irnwlr2aZTBkQ3jUOY4c9IPa2FkYYdBuRASCAL8d0',
#             'rvoCqPpF+xvQF4W1uVjNx14wUcm739LAW+1Uw6VATrxZDp7QRhJd35zDQdwena',
#             'BbWVelqWm2RoTE0BARU6mTHsD3bO1OvwwqBS9uw/scLxpPW0AwlSkksUOSzKI2',
#             'FMNNyn0kKGk2ZJFWUowIDAQAB'
#         ])
#         monkey_text_from_host = "".join([
#             'v=DKIM1\; k=rsa\; ',
#             'p=MIIBIjANBgkqhkiG9wcheQEFAAOCAQ8AMIIBCgKCAQEAy14JM1EVS+y5CsPo',
#             'xvokcnYKlHVownd7A8RqcW0Ndb/PMZy1htsLgskDLwVbwp4TjxaNi6Wxakt0Kz',
#             'xeLT6AC7vmg0zHyMUzy0ra6sWyg3lPfool6wHKlF0ary2KQmbd6yyN+AyiQIT6',
#             'kq+E7hqyElnuAWUjA/Irnwlr2aZTBkQ3jUOY4c9IPa2FkYYdBuRAS" "CAL8d0',
#             'rvoCqPpF+xvQF4W1uVjNx14wUcm739LAW+1Uw6VATrxZDp7QRhJd35zDQdwena',
#             'BbWVelqWm2RoTE0BARU6mTHsD3bO1OvwwqBS9uw/scLxpPW0AwlSkksUOSzKI2',
#             'FMNNyn0kKGk2ZJFWUowIDAQAB'
#         ])
# 
#         class MonkeyDKIM(object):
#             def domainkey(*args, **kwargs):
#                 class OB(object): pass
#                 ob = OB()
#                 ob.subdomain = "foo._domainkey.example.com"
#                 ob.v = "DKIM1"
#                 ob.k = "rsa"
#                 ob.p = "foobar"
#                 ob.text = "RASCAL"
#                 return ob
# 
#         class MonkeyDomain(Domain):
#             def query(self, *args, **kwargs):
#                 return '{} descriptive text "{}"'.format(self.host, monkey_text_from_host)
# 
#         monkey_dns = testdata.patch(dns, Domain=MonkeyDomain, DKIM=MonkeyDKIM)
# 
#         d = monkey_dns.Domain("example.com")
#         self.assertTrue("RASCAL" in d.dkim()[0]["text"])
#         self.assertEqual(monkey_text_valid, d.dkim()[0]["text"])
#         return
# 
#         d = monkey_dns.Alias("example.com", "mail.example.com")
#         dkim = d.needed_dkim()
#         pout.v(dkim[1][1])
#         self.assertTrue("RASCAL" in dkim[1][1])

    def test_domainkey(self):
        d = Domain("example.com")

        monkey_text_valid = "".join([
            'v=DKIM1; k=rsa; ',
            'p=MIIBIjANBgkqhkiG9wcheQEFAAOCAQ8AMIIBCgKCAQEAy14JM1EVS+y5CsPo',
            'xvokcnYKlHVownd7A8RqcW0Ndb/PMZy1htsLgskDLwVbwp4TjxaNi6Wxakt0Kz',
            'xeLT6AC7vmg0zHyMUzy0ra6sWyg3lPfool6wHKlF0ary2KQmbd6yyN+AyiQIT6',
            'kq+E7hqyElnuAWUjA/Irnwlr2aZTBkQ3jUOY4c9IPa2FkYYdBuRASCAL8d0',
            'rvoCqPpF+xvQF4W1uVjNx14wUcm739LAW+1Uw6VATrxZDp7QRhJd35zDQdwena',
            'BbWVelqWm2RoTE0BARU6mTHsD3bO1OvwwqBS9uw/scLxpPW0AwlSkksUOSzKI2',
            'FMNNyn0kKGk2ZJFWUowIDAQAB'
        ])
        monkey_text_from_host = "".join([
            'v=DKIM1\; k=rsa\; ',
            'p=MIIBIjANBgkqhkiG9wcheQEFAAOCAQ8AMIIBCgKCAQEAy14JM1EVS+y5CsPo',
            'xvokcnYKlHVownd7A8RqcW0Ndb/PMZy1htsLgskDLwVbwp4TjxaNi6Wxakt0Kz',
            'xeLT6AC7vmg0zHyMUzy0ra6sWyg3lPfool6wHKlF0ary2KQmbd6yyN+AyiQIT6',
            'kq+E7hqyElnuAWUjA/Irnwlr2aZTBkQ3jUOY4c9IPa2FkYYdBuRAS" "CAL8d0',
            'rvoCqPpF+xvQF4W1uVjNx14wUcm739LAW+1Uw6VATrxZDp7QRhJd35zDQdwena',
            'BbWVelqWm2RoTE0BARU6mTHsD3bO1OvwwqBS9uw/scLxpPW0AwlSkksUOSzKI2',
            'FMNNyn0kKGk2ZJFWUowIDAQAB'
        ])
        def monkey_query(self, *args, **kwargs):
            return '{} descriptive text "{}"'.format(self.host, monkey_text_from_host)

        testdata.patch(d, query=monkey_query)

        self.assertTrue("RASCAL" in d.dkim()[0]["text"])
        self.assertEqual(monkey_text_valid, d.dkim()[0]["text"])

# class MailserverTest(TestCase):
#     def test_

