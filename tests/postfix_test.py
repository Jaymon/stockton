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





