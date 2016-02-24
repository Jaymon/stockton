from unittest import TestCase

from stockton import postfixconfig as postfix


def setUpModule():
    pass


def tearDownModule():
    pass


class PostfixTestCase(TestCase):
    def test_master(self):
        master_path = testdata.create_file("master.cf", "\n".join([
            "#",
            "# this is the stuff before the first section",
            "#",
#             "# ==========================================================================",
#             "# service type  private unpriv  chroot  wakeup  maxproc command + args",
#             "#               (yes)   (yes)   (yes)   (never) (100)",
#             "# ==========================================================================",
            "smtp      inet  n       -       -       -       -       smtpd",
        ]))

        master = postfix.Master(prototype_path=master_path)
