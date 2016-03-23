from unittest import TestCase
import time

import testdata

from stockton import cli


class CliTest(TestCase):
    def test_cached_run(self):
        cmd = "date; sleep 1; date"
        r = cli.cached_run(cmd)

        start = time.time()
        r2 = cli.cached_run(cmd)
        stop = time.time()
        self.assertEqual(r, r2)
        self.assertTrue((stop - start) < 1)

        time.sleep(1.1)
        r3 = cli.cached_run(cmd, ttl=1)
        self.assertNotEqual(r, r3)

    def test_ip(self):
        ip = cli.ip()
        ip2 = cli.ip()
