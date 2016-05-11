# thanks to
# http://seasonofcode.com/posts/setting-up-dkim-and-srs-in-postfix.html
# http://serverfault.com/questions/82234/srs-sender-rewriting-when-forwarding-mail-through-postfix
# http://www.mind-it.info/2014/02/22/forward-postfix-spf-srs/
# http://www.openspf.org/SRS

import re

from .. import cli
from ..path import Dirpath, Filepath, Sentinal
from .base import Interface


class SRS(Interface):
    @property
    def temp_d(self):
        return Dirpath.get_temp()

    @property
    def build_d(self):
        build_d = Dirpath(self.temp_d, "postsrsd-master", "build")
        return build_d

    def start(self):
        try:
            cli.run("start postsrsd")
        except RuntimeError as e:
            if not re.search("Job\s+is\s+already\s+running", str(e), re.I):
                raise

    def restart(self):
        if self.is_running():
            cli.run("restart postsrsd")

        else:
            self.start()

    def stop(self):
        cli.run("stop postsrsd")

    def is_running(self):
        ret = True
        output = cli.run("status postsrsd")
        if re.search("stop", output, flags=re.I):
            ret = False
        return ret

    def install(self):
        #cli.package("unzip", "cmake", "curl", "build-essential")
        cli.package("unzip", "cmake", "build-essential")

        tmpdir = self.temp_d

        # only download the srs if it doesn't already exist
        postsrs_f = Filepath(tmpdir, "postsrsd.zip")
        with Sentinal.check("srs") as s:
            if not s:
                # https://github.com/roehling/postsrsd
                cli.run("wget -O postsrsd.zip https://github.com/roehling/postsrsd/archive/master.zip", cwd=tmpdir.path)
                #cli.run("curl -L -o postsrsd.zip https://github.com/roehling/postsrsd/archive/master.zip", cwd=tmpdir.path)

        # Build and install.
        cli.run("unzip -o postsrsd.zip", cwd=tmpdir.path)
        build_d = self.build_d
        build_d.create()

        cli.run("cmake -DCMAKE_INSTALL_PREFIX=/usr ../", cwd=build_d.path)
        cli.run("make", cwd=build_d.path)
        cli.run("make install", cwd=build_d.path)

