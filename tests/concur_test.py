from unittest import TestCase

import testdata

from stockton import postfixconfig as postfix


def setUpModule():
    pass


def tearDownModule():
    pass


class PostfixTestCase(TestCase):

    def test_master_option(self):
        class FP(object):
            line = "  -o smtpd_tls_wrappermode=yes"

        mo = postfix.MasterOption()
        mo.parse(FP())
        pout.v(mo)

    def test_master(self):
        master_path = testdata.create_file("master.cf", "\n".join([
#             "#",
#             "# this is the stuff before the first section",
#             "#",
#             "# ==========================================================================",
#             "# service type  private unpriv  chroot  wakeup  maxproc command + args",
#             "#               (yes)   (yes)   (yes)   (never) (100)",
#             "# ==========================================================================",
            "smtp      inet  n       -       -       -       -       smtpd",
            "  -o smtpd_tls_wrappermode=yes",
            "  -o smtpd_sasl_auth_enable=yes",
            "  -o smtpd_client_restrictions=permit_sasl_authenticated,reject",
            "  -o milter_macro_daemon_name=ORIGINATING",
        ]))

        master = postfix.Master(prototype_path=master_path)
        pout.v(str(master))
