from unittest import TestCase

import testdata

from stockton.dns import Domain


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


# class MailserverTest(TestCase):
#     def test_

