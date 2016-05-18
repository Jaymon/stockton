import re

from captain import echo

from .. import cli
from .postfix import Postfix
from ..path import Filepath, Dirpath
#from ..concur.formats.opendkim import OpenDKIM
from ..concur.formats.spamassassin import SpamAssassin, Local


class Spam(object):

    @property
    def user(self):
        return "debian-spamd"

    @property
    def home_d(self):
        # http://askubuntu.com/questions/410244/a-command-to-list-all-users-and-how-to-add-delete-modify-users
        username = self.user
        path = cli.run(
            'grep "{}" /etc/passwd | cut -f6 -d":"'.format(username),
            capture_output=True
        ).strip()

        if not path:
            raise ValueError("could not find home directory for user {}".format(username))

        return Dirpath(path)

    @property
    def config_f(self):
        return Filepath(SpamAssassin.dest_path)

    @property
    def local_f(self):
        return Filepath(Local.dest_path)

    def base_configs(self):
        return [self.config_f, self.local_f]

    def config(self, path=SpamAssassin.dest_path):
        return SpamAssassin(prototype_path=path)

    def local(self, path=Local.dest_path):
        return Local(prototype_path=path)

    def start(self):
        try:
            o = cli.run("/etc/init.d/spamassassin start")
        except RuntimeError as e:
            if not re.search("already\s+running", str(e), re.I):
                raise

    def restart(self):
        if self.is_running():
            cli.run("/etc/init.d/spamassassin restart")
        else:
            self.start()

    def stop(self):
        cli.run("/etc/init.d/spamassassin stop")

    def is_running(self):
        ret = True
        try:
            cli.run("/etc/init.d/spamassassin status")
        except RuntimeError:
            ret = False
        return ret

    def exists(self):
        ret = True
        try:
            self.stop()
        except cli.RunError as e:
            ret = not e.is_missing()
        return ret


    def install(self):
        # make sure the packages are installed
        cli.package("spamassassin", "spamc")

        # add the spam user
        # update 4-16-2016 let's just use debian-spamd and /var/lib/spamassassin
        #cli.run("adduser --disabled-login --disabled-password --gecos "" spamd")
        if not self.home_d.exists():
            raise ValueError("Home directory {} does not exist".format(self.home_d))

    def uninstall(self):
        try:
            self.stop()
        except cli.RunError as e:
            if not e.is_missing():
                raise

        cli.purge("spamassassin", "spamc")

