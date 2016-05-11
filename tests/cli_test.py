from unittest import TestCase
import time
import os

import testdata

from stockton import cli


class CliTest(TestCase):
    def test_stderr(self):
        filepath = testdata.create_file("errpipe.sh", [
            'echo "1" 1>&2',
            '(>&2 echo "2")',
            'echo "3" >&2'
        ])
        os.chmod(filepath, 0o755)
        #cmd = "echo 'foobar' 1>&2"
        #cmd = "/vagrant/errpipe.sh"
        output = cli.run(filepath)
        for x in range(1, 4):
            self.assertTrue(str(x) in output)

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
