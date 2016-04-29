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

    def config(self, prototype_path=SpamAssassin.dest_path):
        return SpamAssassin(prototype_path=prototype_path)

    def local(self, prototype_path=Local.dest_path):
        return Local(prototype_path=prototype_path)

    def restart(self):
        try:
            cli.run("/etc/init.d/spamassassin status", capture_output=True)

        except RuntimeError:
            cli.run("/etc/init.d/spamassassin start")

        else:
            cli.run("/etc/init.d/spamassassin restart")

    def install(self):
        # make sure the packages are installed
        cli.package("spamassassin", "spamc")

        # add the spam user
        # update 4-16-2016 let's just use debian-spamd and /var/lib/spamassassin
        #cli.run("adduser --disabled-login --disabled-password --gecos "" spamd")
        if not self.home_d.exists():
            raise ValueError("Home directory {} does not exist".format(self.home_d))

    def is_running(self):
        ret = True
        try:
            cli.running("spamd")
        except RuntimeError:
            ret = False

        return ret

