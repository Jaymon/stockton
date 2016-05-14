from unittest import TestCase as BaseTestCase, SkipTest
import os

from captain.client import Captain


class TestCase(BaseTestCase):
    @classmethod
    def setup_env(cls):
        pass

    @classmethod
    def setUpClass(cls):
        if os.environ["USER"] != "root":
            raise RuntimeError("User is not root, re-run this test with sudo")

        cls.setup_env()


class Stockton(Captain):
    """The command line runner for running one of the cli commands"""

    script_quiet = False

    def __init__(self, subcommand):
        self.cmd_prefix = "python -m stockton --verbose {}".format(subcommand.replace("_", "-"))
        super(Stockton, self).__init__("")

